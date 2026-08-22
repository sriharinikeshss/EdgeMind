import { Chat } from './components/Chat'
import './App.css'

function App() {
  return (
    <div className="app-container">
      <header className="app-header">
        <h1>EdgeMind KAVACH Workbench</h1>
        <p>Sovereign On-Premise Agentic AI</p>
      </header>
      <main>
        <Chat />
      </main>
    </div>
  )
}

export default App
