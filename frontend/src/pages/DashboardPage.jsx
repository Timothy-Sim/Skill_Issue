import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Sidebar from './Sidebar'

const API_URL = import.meta.env.REACT_APP_API_URL || import.meta.env.VITE_REACT_APP_API_URL;

const API = API_URL ? `${API_URL}` : "http://localhost:5000"; 

// Helper function to format month and year (e.g., "2023-01")
const getMonthYearString = (date) => {
    const year = date.getFullYear();
    // Months are 0-indexed, so we add 1 and pad with '0'
    const month = String(date.getMonth() + 1).padStart(2, '0');
    return `${year}-${month}`;
};

// Helper function to get the current and previous 12 month-year strings
const getMonthYearOptions = (count = 24) => {
    const options = [];
    let date = new Date(); // Start with the current date (for the latest month)
    
    // Set the date to the first day of the current month to ensure consistency
    date.setDate(1); 
    
    for (let i = 0; i < count; i++) {
        options.push(getMonthYearString(date));
        // Move back one month
        date.setMonth(date.getMonth() - 1);
    }
    return options.reverse(); // Reverse to show oldest first
};

const monthYearOptions = getMonthYearOptions();


export default function DashboardPage() {
  const [userInfo, setUserInfo] = useState(null);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  // State for the "Link Account" form
  const [linkUsername, setLinkUsername] = useState('');
  const [linkMessage, setLinkMessage] = useState('');

  // ⭐️ NEW: State for the date range
  const [startMonthYear, setStartMonthYear] = useState(monthYearOptions[monthYearOptions.length - 6] || ''); // Default to 6 months ago
  const [endMonthYear, setEndMonthYear] = useState(monthYearOptions[monthYearOptions.length - 1] || '');   // Default to the most recent month

  // State for analysis
  const [analysisResults, setAnalysisResults] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  
  const navigate = useNavigate();

  // Function to fetch user status (we'll call this on load and after linking)
  const fetchUserStatus = async () => {
    try {
      // Fetch with credentials to send the session cookie
      const response = await fetch(`${API}/api/user/status`, {
        method: 'GET',
        credentials: 'include', // Important: sends cookies
      });
      
      if (!response.ok) {
        throw new Error('Network response was not ok');
      }

      const data = await response.json();
      if (data.logged_in) {
        setIsLoggedIn(true);
        setUserInfo(data.user_info);
      } else {
        setIsLoggedIn(false);
        navigate('/login?error=session_expired'); // Redirect if not logged in
      }
    } catch (err) {
      setError('Failed to fetch user status. Please try refreshing.');
      setIsLoggedIn(false);
    } finally {
      setLoading(false);
    }
  };

  // Fetch user status on component load
  useEffect(() => {
    fetchUserStatus();
  }, [navigate]); // Add navigate as a dependency

  // Handler for the "Link Account" form (no change needed here)
  const handleLinkAccount = async (e) => {
    e.preventDefault();
    setLinkMessage(''); // Clear previous messages
    if (!linkUsername) {
      setLinkMessage('Please enter a username.');
      return;
    }

    try {
      const response = await fetch(`${API}/api/user/link_chess_account`, {
        method: 'POST',
        credentials: 'include', // Send cookies
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username: linkUsername }),
      });
      
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to link account');
      }

      setLinkMessage(data.message || 'Account linked!');
      // Refresh user info to show the new "Analyze" button
      await fetchUserStatus(); 
      setLinkUsername(''); // Clear input
      
    } catch (err) {
      setLinkMessage(err.message);
    }
  };

  // Handler for the "Analyze" button
  const handleAnalyze = async () => {
    // ⭐️ NEW: Date validation
    if (startMonthYear > endMonthYear) {
        setError('Start date cannot be after the end date.');
        return;
    }

    setAnalysisResults(null);
    setAnalysisLoading(true);
    setError('');

    try {
      const response = await fetch(`${API}/api/analyze`, {
        method: 'POST',
        credentials: 'include', // Send cookies
        headers: {
            'Content-Type': 'application/json',
        },
        // ⭐️ NEW: Send the date range in the request body
        body: JSON.stringify({ 
            start_month_year: startMonthYear, 
            end_month_year: endMonthYear 
        }),
      });
      
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Analysis failed');
      }
      
      setAnalysisResults(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setAnalysisLoading(false);
    }
  };

  // Show loading spinner while checking auth
  if (loading) {
    return <div className="min-h-screen bg-gray-100 flex items-center justify-center"><p>Loading...</p></div>;
  }
  
  // Show this if user is somehow not logged in
  if (!isLoggedIn) {
      // This shouldn't be seen if the useEffect redirect works, but it's good practice
    return <div className="min-h-screen bg-gray-100 flex items-center justify-center"><p>Please <a href="/login" className="text-blue-600">login</a>.</p></div>;
  }

  // Main dashboard content
  return (
    <Sidebar>
    <div className="w-full">
      <div className="max-w-4xl mx-auto bg-white p-6 rounded-lg shadow-md">
        
        <div className="mb-4">
          <h1 className="text-3xl font-bold text-gray-900">
            Welcome, {userInfo?.name || 'User'}!
          </h1>
        </div>

        <hr className="my-6" />

        {/* === CONDITIONAL SECTION === */}
        {/* Check if chess_com_username is linked */}
        {!userInfo?.chess_com_username ? (
          // STATE 1: No username is linked
          <div>
            <h2 className="text-2xl font-semibold mb-4">Link Your Chess.com Account</h2>
            <p className="text-gray-600 mb-4">
              To begin analyzing your games, please link your Chess.com account.
            </p>
            <form onSubmit={handleLinkAccount}>
              <label htmlFor="link-username" className="block text-sm font-medium text-gray-700">
                Chess.com Username
              </label>
              <div className="mt-1 flex rounded-md shadow-sm">
                <input
                  type="text"
                  id="link-username"
                  value={linkUsername}
                  onChange={(e) => setLinkUsername(e.target.value)}
                  className="flex-1 block w-full rounded-none rounded-l-md border-gray-300 focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2"
                  placeholder="e.g., Hikaru"
                />
                <button
                  type="submit"
                  className="inline-flex items-center rounded-r-md border border-l-0 border-gray-300 bg-gray-50 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
                >
                  Link Account
                </button>
              </div>
              {linkMessage && (
                <p className={`mt-2 text-sm ${linkMessage.includes('failed') || linkMessage.includes('Error') || linkMessage.includes('already linked') ? 'text-red-600' : 'text-green-600'}`}>
                  {linkMessage}
                </p>
              )}
            </form>
          </div>
        ) : (
          // STATE 2: Username is linked
          <div>
            <h2 className="text-2xl font-semibold mb-4">Analyze Your Games</h2>
            <p className="text-gray-600 mb-4">
              Your linked Chess.com account: <strong className="text-gray-900">{userInfo.chess_com_username}</strong>
            </p>
            
            {/* ⭐️ NEW: Date Range Selectors */}
            <div className="mb-4 p-4 border border-gray-200 rounded-md">
                <h3 className="text-lg font-medium mb-3">Select Game Date Range</h3>
                <div className="flex space-x-4">
                    <div className="flex-1">
                        <label htmlFor="start-month" className="block text-sm font-medium text-gray-700">
                            Start Month/Year
                        </label>
                        <select
                            id="start-month"
                            value={startMonthYear}
                            onChange={(e) => setStartMonthYear(e.target.value)}
                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm py-2"
                        >
                            {monthYearOptions.map(my => (
                                <option key={my} value={my}>{my}</option>
                            ))}
                        </select>
                    </div>
                    <div className="flex-1">
                        <label htmlFor="end-month" className="block text-sm font-medium text-gray-700">
                            End Month/Year
                        </label>
                        <select
                            id="end-month"
                            value={endMonthYear}
                            onChange={(e) => setEndMonthYear(e.target.value)}
                            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm py-2"
                        >
                            {monthYearOptions.map(my => (
                                <option key={my} value={my}>{my}</option>
                            ))}
                        </select>
                    </div>
                </div>
            </div>
            
            <p className="text-gray-600 mb-4">
              Click the button below to fetch and analyze your games within the selected range.
            </p>
            <button
              onClick={handleAnalyze}
              disabled={analysisLoading}
              className="px-6 py-2 bg-indigo-600 text-white font-semibold rounded-md shadow-sm hover:bg-indigo-500 disabled:bg-gray-400"
            >
              {analysisLoading ? 'Analyzing...' : 'Analyze Selected Games'}
            </button>
            <p className="text-sm text-gray-500 mt-2">
              Want to analyze a different account? You can change your linked account on your Profile page (coming soon).
            </p>
          </div>
        )}

        {/* === Analysis Results Section === */}
        {error && (
          <div className="mt-6 p-4 bg-red-100 text-red-700 rounded-md">
            <h3 className="font-bold">Error</h3>
            <p>{error}</p>
          </div>
        )}
        
        {analysisResults && (
          <div className="mt-6">
            <h2 className="text-2xl font-semibold mb-4">Analysis Results</h2>
            <pre className="bg-gray-900 text-white p-4 rounded-md overflow-x-auto">
              {JSON.stringify(analysisResults, null, 2)}
            </pre>
          </div>
        )}

      </div>
    </div>
    </Sidebar>
  );
}