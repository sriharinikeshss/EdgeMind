/**
 * App.tsx - EdgeMind KAVACH
 */
import { AuthProvider, useAuth } from "./context/AuthContext";
import { Chat } from "./components/Chat";
import { Login } from "./pages/Login";
import "./App.css";

function AppInner() {
  const { isAuthenticated, user, logout } = useAuth();

  if (!isAuthenticated) {
    return <Login onSuccess={() => {}} />;
  }

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="header-left">
          <span className="header-logo">🧠</span>
          <div>
            <h1>EdgeMind KAVACH Workbench</h1>
            <p>Sovereign On-Premise Agentic AI</p>
          </div>
        </div>
        <div className="header-right">
          <span className="user-badge">
            👤 {user?.username} <em>({user?.role})</em>
          </span>
          <button className="logout-btn" onClick={logout}>Sign Out</button>
        </div>
      </header>
      <main>
        <Chat />
      </main>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppInner />
    </AuthProvider>
  );
}

export default App;
