import os
import psycopg2
from dotenv import load_dotenv
import numpy as np
import pandas as pd
import gower
import hdbscan
import json

# --- Key Imports from Scikit-learn ---
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.compose import ColumnTransformer
from sklearn.exceptions import NotFittedError

from . import db_helpers # Use relative import

# --- 1. Feature Definitions (v6.3 / v9 Logic) ---

NUMERIC_COLS = ['cpl', 'move_number']

CATEGORICAL_COLS = [
    'mistake_type', 'mistake_category', 'game_phase', 'material_balance', 
    'board_complexity', 'king_self_safety', 'king_opponent_status', 
    'castling_status_self', 'piece_moved', 'move_type', 'piece_was_attacked', 
    'piece_was_defended', 'piece_was_defending', 'piece_was_pinned'
]

CONTEXT_TRIGGERS = [
    'game_phase_', 'material_balance_', 'board_complexity_', 'castling_status_'
]
ACTION_TRIGGERS = [
    'mistake_type_', 'mistake_category_', # We include these as triggers now
    'piece_moved_', 'move_type_', 'piece_was_attacked_', 'piece_was_defended_',
    'piece_was_defending_', 'piece_was_pinned_', 'king_self_safety_', 'king_opponent_status_'
]

TRANSLATIONS = {
    'game_phase_Middlegame': 'in the middlegame',
    'game_phase_Opening': 'in the opening',
    'game_phase_Endgame': 'in the endgame',
    'piece_moved_KNIGHT': 'you move your knight',
    'piece_moved_QUEEN': 'you move your queen',
    'king_self_safety_Exposed': 'your king is exposed',
    'king_self_safety_Safe': 'your king is safe',
    'piece_was_attacked_True': 'your piece is under attack',
    'castling_status_self_Can_Castle': 'before you have castled',
    'castling_status_self_Has_Castled': 'after you have castled',
    'mistake_category_Positional_Error': 'a positional error',
    'mistake_category_Hanging_Piece': 'a hanging piece',
    # Add more as you discover them
}

# --- 2. Main Analysis Pipeline ---

def main_analysis_pipeline(user_id, conn):
    """
    Main v9 pipeline:
    1. Clears old analysis.
    2. Fetches all mistakes.
    3. Runs HDBSCAN to find "Habit Archetypes".
    4. For each habit, runs L1 Model (One-vs-All) to find triggers.
    5. Saves new feedback and links mistakes.
    """
    
    with conn.cursor() as cur:
        # 1. Clear old habits and feedback
        db_helpers.clear_old_habits_and_feedback(cur, user_id)
        
        # 2. Get all mistake data
        all_mistakes = db_helpers.get_all_mistakes_for_user_v6(cur, user_id)
        
        if len(all_mistakes) < 20: 
            print("Not enough mistakes to run analysis.")
            return {"new_habits_found": 0, "total_mistakes": len(all_mistakes)}
            
        df = pd.DataFrame(all_mistakes).set_index('id') 
        
        # 3. Step 1 (v9): Habit Discovery (HDBSCAN)
        print(f"\n--- Running Step 1: Habit Discovery (HDBSCAN) on {len(df)} mistakes ---")
        df_clustered = _run_hdbscan_clustering(df)
        
        # 4. Separate noise from habits
        noise_df = df_clustered[df_clustered['habit_id'] == -1]
        habits_df = df_clustered[df_clustered['habit_id'] != -1]
        
        if habits_df.empty:
            print("HDBSCAN found no significant habits. Only noise.")
            return {"new_habits_found": 0, "total_mistakes": len(all_mistakes)}

        print(f"HDBSCAN found {habits_df['habit_id'].nunique()} habits and {len(noise_df)} noise points.")
        
        # 5. Step 2 (v9): Trigger Identification (L1 Model)
        print("\n--- Running Step 2: Trigger Identification (L1 Logistic Regression) ---")
        
        preprocessor = _create_feature_preprocessor(df)
        if preprocessor is None:
             print("Failed to create feature preprocessor. Aborting analysis.")
             return {"new_habits_found": 0, "total_mistakes": len(all_mistakes)}

        new_habit_count = 0
        
        for hdbscan_label in habits_df['habit_id'].unique():
            print(f"\n--- Analyzing Habit Cluster {hdbscan_label} ---")
            cluster_df = habits_df[habits_df['habit_id'] == hdbscan_label]
            
            # Use "One-vs-All" (Habit vs. All Other Mistakes, including noise)
            control_df = df_clustered[df_clustered['habit_id'] != hdbscan_label]
            
            model, feature_names = _find_triggers_for_cluster(cluster_df, control_df, preprocessor)
            
            if model is None:
                continue
                
            # 6. Step 3 (v9): Generate, Save, and Link
            new_serial_id = _generate_and_save_feedback(
                cur, user_id, hdbscan_label, cluster_df, model, feature_names
            )
            
            if new_serial_id:
                # Link all mistakes in this cluster to the new habit ID
                list_of_mistake_ids = cluster_df.index.tolist()
                db_helpers.link_mistakes_to_habit(cur, new_serial_id, list_of_mistake_ids)
                new_habit_count += 1

        print(f"\nAnalysis pipeline complete for user {user_id}")
        return {"new_habits_found": new_habit_count, "total_mistakes": len(all_mistakes)}

# --- 3. Pipeline Helper Functions ---

def _run_hdbscan_clustering(df):
    """
    Prepares data and runs HDBSCAN to find clusters.
    """
    df_features = df.copy()
    
    scaler = StandardScaler()
    df_features[NUMERIC_COLS] = scaler.fit_transform(df_features[NUMERIC_COLS])
    
    for col in CATEGORICAL_COLS:
        df_features[col] = df_features[col].astype(str).fillna('None')

    print("Computing Gower distance matrix...")
    gower_matrix = gower.gower_matrix(df_features[NUMERIC_COLS + CATEGORICAL_COLS])
    gower_matrix_double = gower_matrix.astype(np.float64)

    print("Running HDBSCAN...")
    clusterer = hdbscan.HDBSCAN(
        metric='precomputed',
        min_cluster_size=5, # Find habits with as few as 5 mistakes
        min_samples=3,
        allow_single_cluster=False,
        gen_min_span_tree=True
    )
    clusterer.fit(gower_matrix_double)
    
    df['habit_id'] = clusterer.labels_
    df['habit_confidence'] = clusterer.probabilities_
    return df

def _create_feature_preprocessor(df):
    """
    Creates a scikit-learn ColumnTransformer to one-hot encode
    categorical features for the Logistic Regression model.
    """
    try:
        # Fill NAs and ensure string type for encoder
        df_cat = df[CATEGORICAL_COLS].astype(str).fillna('None')
        
        preprocessor = ColumnTransformer(
            transformers=[
                ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), CATEGORICAL_COLS)
            ],
            remainder='drop' 
        )
        
        preprocessor.fit(df_cat)
        return preprocessor
    except Exception as e:
        print(f"Error creating preprocessor: {e}")
        return None

def _find_triggers_for_cluster(cluster_df, control_df, preprocessor):
    """
    Trains a balanced L1 Logistic Regression model (Habit vs. Control).
    """
    positive_df = cluster_df
    negative_df = control_df
    
    if negative_df.empty:
        print("Cannot train model: No 'control' examples to compare against.")
        return None, None
        
    training_df = pd.concat([positive_df, negative_df])
    Y_train = (training_df['habit_id'] == cluster_df['habit_id'].iloc[0]).astype(int) 
    
    X_train_raw = training_df[CATEGORICAL_COLS].astype(str).fillna('None')
    
    try:
        X_train_processed = preprocessor.transform(X_train_raw)
    except Exception as e:
        print(f"Error during feature transformation: {e}")
        return None, None
    
    feature_names = list(preprocessor.named_transformers_['cat'].get_feature_names_out(CATEGORICAL_COLS))

    model = LogisticRegression(
        penalty='l1', 
        solver='liblinear', 
        class_weight='balanced', 
        C=1.0, # Use 1.0 for less strict regularization
        random_state=42
    )
    model.fit(X_train_processed, Y_train)
    
    return model, feature_names
    
def _generate_and_save_feedback(cur, user_id, hdbscan_label, cluster_df, model, feature_names):
    """
    Extracts triggers (v6.3 logic), finds "worst offense," and saves feedback.
    """
    coefficients = model.coef_[0]
    # Get features with a meaningful *positive* association
    triggers = {name: coef for name, coef in zip(feature_names, coefficients) if coef > 0.1} 
    
    if not triggers:
        print(f"No positive triggers found for Habit {hdbscan_label}.")
        return None

    # Separate into Context and Action
    context_triggers = {f: c for f, c in triggers.items() if any(t in f for t in CONTEXT_TRIGGERS)}
    action_triggers = {f: c for f, c in triggers.items() if any(t in f for t in ACTION_TRIGGERS)}

    top_context = max(context_triggers, key=context_triggers.get, default=None)
    top_action = max(action_triggers, key=action_triggers.get, default=None)

    habit_confidence = cluster_df['habit_confidence'].mean()
    prime_example_id = int(cluster_df['cpl'].idxmax()) 
    
    feedback_text, habit_name = _build_feedback_sentence(top_context, top_action, habit_confidence)
    
    print(f"Generated feedback for cluster {hdbscan_label}: {feedback_text}")
    
    # Save to DB and get the new serial ID
    new_serial_habit_id = db_helpers.save_habit_analysis(
        cur, 
        user_id, 
        hdbscan_label, # The HDBSCAN cluster label
        habit_name,
        json.dumps(triggers), 
        habit_confidence, 
        prime_example_id, 
        feedback_text
    )
    return new_serial_habit_id

def _build_feedback_sentence(context, action, confidence):
    """
    Simple translator for building the final feedback and habit name.
    """
    conf_str = f"({confidence * 100:.0f}% confidence)"
    
    ctx_str = TRANSLATIONS.get(context, context.replace("_", " ").lower() if context else "")
    act_str = TRANSLATIONS.get(action, action.replace("_", " ").lower() if action else "")
    
    if context and action:
        habit_name = f"{ctx_str.capitalize()}: {act_str.capitalize()}"
        feedback = f"We've found a recurring pattern {conf_str}: **{ctx_str}**, you tend to make mistakes when **{act_str}**."
    elif action:
        habit_name = f"{act_str.capitalize()} Mistakes"
        feedback = f"We've found a recurring pattern {conf_str}: You have a pattern of making mistakes when **{act_str}**."
    elif context:
        habit_name = f"{ctx_str.capitalize()} Mistakes"
        feedback = f"We've found a recurring pattern {conf_str}: You have a pattern of making mistakes **{ctx_str}**."
    else:
        habit_name = "General Pattern"
        feedback = f"We've found a recurring pattern {conf_str}, but we could not isolate a single clear trigger."
        
    return feedback, habit_name