import './App.css'
import { useCurrentUser } from './auth/AuthContext'

function App() {
  const { user, isAuthenticated, isLoading, login, logout } = useCurrentUser()

  if (isLoading) return null

  if (!isAuthenticated) {
    return (
      <section id="center">
        <div>
          <h1>spreadsheet-analyser</h1>
          <p>Sign in with your account to continue.</p>
        </div>
        <button type="button" className="counter" onClick={() => login()}>
          Log in
        </button>
      </section>
    )
  }

  return (
    <section id="center">
      <div>
        <h1>Welcome, {user?.name}</h1>
        <p>{user?.email}</p>
      </div>
      <button type="button" className="counter" onClick={() => logout()}>
        Log out
      </button>
    </section>
  )
}

export default App
