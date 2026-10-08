import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Home, LineChart, TestTube2 } from 'lucide-react';
import PredictionForm from './pages/PredictionForm';
import Analytics from './pages/Analytics';

function NavLinks() {
  const location = useLocation();
  const isActive = (path: string) => location.pathname === path;

  return (
    <nav className="mt-6">
      <Link 
        to="/" 
        className={`flex items-center gap-3 px-6 py-3 transition-colors ${
          isActive('/') ? 'bg-blue-50 text-blue-600 border-r-4 border-blue-600' : 'text-gray-700 hover:bg-blue-50 hover:text-blue-600'
        }`}
      >
        <Home size={20} />
        Prediction
      </Link>
      <Link 
        to="/analytics" 
        className={`flex items-center gap-3 px-6 py-3 transition-colors ${
          isActive('/analytics') ? 'bg-blue-50 text-blue-600 border-r-4 border-blue-600' : 'text-gray-700 hover:bg-blue-50 hover:text-blue-600'
        }`}
      >
        <LineChart size={20} />
        Analytics
      </Link>
    </nav>
  );
}

function App() {
  return (
    <Router>
      <div className="flex h-screen bg-gray-50 font-sans">
        {/* Sidebar */}
        <aside className="w-64 bg-white shadow-sm border-r border-gray-200">
          <div className="p-6">
            <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
              <TestTube2 className="text-blue-600" /> AI Materials
            </h1>
          </div>
          <NavLinks />
        </aside>

        {/* Main Content */}
        <main className="flex-1 overflow-y-auto p-8">
          <Routes>
            <Route path="/" element={<PredictionForm />} />
            <Route path="/analytics" element={<Analytics />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
