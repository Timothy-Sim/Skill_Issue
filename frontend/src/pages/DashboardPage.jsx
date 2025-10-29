import React, { useState, useEffect } from 'react';

export default function DashboardPage() {
  const [userInfo, setUserInfo] = useState(null);
  const [loadingUser, setLoadingUser] = useState(true);
  const [chessUsername, setChessUsername] = useState('');
  const [analysisResults, setAnalysisResults] = useState(null);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [analysisError, setAnalysisError] = useState('');

  // Fetch user status on component mount
  useEffect(() => {
    const fetchUserStatus = async () => {
      try {
        setLoadingUser(true);
        // Use credentials: 'include' to send session cookies
        const response = await fetch('http://localhost:5000/api/user/status', {credentials: 'include'});
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        if (data.logged_in) {
          setUserInfo(data.user_info);
        } else {
          // Handle case where user is somehow not logged in
          // Maybe redirect back to login?
           window.location.href = '/login?error=not_logged_in';
        }
      } catch (error) {
        console.error("Failed to fetch user status:", error);
        // Handle error, maybe redirect to login
         window.location.href = '/login?error=status_fetch_failed';
      } finally {
        setLoadingUser(false);
      }
    };

    fetchUserStatus();
  }, []); // Empty dependency array means this runs once on mount

  // Handle analysis form submission
  const handleAnalyzeSubmit = async (e) => {
    e.preventDefault();
    setLoadingAnalysis(true);
    setAnalysisResults(null);
    setAnalysisError('');

    try {
      const response = await fetch('http://localhost:5000/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // Use credentials: 'include' is needed to send session cookie for protected route
        credentials: 'include',
        body: JSON.stringify({ username: chessUsername })
      });

      if (!response.ok) {
         const errorData = await response.json();
         throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setAnalysisResults(data);
    } catch (error) {
       console.error("Analysis failed:", error);
       setAnalysisError(error.message || "Failed to analyze games.");
    } finally {
      setLoadingAnalysis(false);
    }
  };

  if (loadingUser) {
    return <div className="min-h-screen bg-gray-100 flex items-center justify-center">Loading user info...</div>;
  }

  if (!userInfo) {
     // This shouldn't be reached if the redirect works, but good as a fallback
    return <div className="min-h-screen bg-gray-100 flex items-center justify-center">Could not load user info. Please try logging in again.</div>;
  }

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-4xl mx-auto bg-white p-6 rounded-lg shadow-md">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Skill Issue Dashboard</h1>
            <p className="text-gray-600">Welcome, {userInfo.name || userInfo.email}!</p>
          </div>
          <a
            href="http://localhost:5000/logout" // Link to backend logout
            className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700"
          >
            Logout
          </a>
        </div>

        {/* Analysis Form */}
        <form onSubmit={handleAnalyzeSubmit} className="mb-8">
          <label htmlFor="chessUsername" className="block text-sm font-medium text-gray-700 mb-1">
            Enter Chess.com Username to Analyze
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              id="chessUsername"
              value={chessUsername}
              onChange={(e) => setChessUsername(e.target.value)}
              className="flex-grow block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
              placeholder="e.g., hikaru"
            />
            <button
              type="submit"
              disabled={loadingAnalysis}
              className={`px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white ${
                loadingAnalysis ? 'bg-indigo-300' : 'bg-indigo-600 hover:bg-indigo-700'
              } focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500`}
            >
              {loadingAnalysis ? 'Analyzing...' : 'Analyze Games'}
            </button>
          </div>
        </form>

        {/* Analysis Results */}
        {analysisError && (
            <div className="mt-4 p-4 bg-red-100 text-red-700 border border-red-300 rounded-md">
                <p><strong>Error:</strong> {analysisError}</p>
            </div>
        )}
        {analysisResults && (
          <div className="mt-6">
            <h2 className="text-xl font-semibold text-gray-800">Analysis Results</h2>
            <pre className="mt-2 p-4 bg-gray-800 text-white rounded-md overflow-x-auto text-sm">
              {JSON.stringify(analysisResults, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
