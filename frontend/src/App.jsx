import { useEffect, useState } from 'react'

function App() {
  const [message, setMessage] = useState('Loading...')

  useEffect(() => {
    fetch('http://localhost:8000/')
      .then((r) => r.json())
      .then((data) => setMessage(data.message))
      .catch(() => setMessage('Could not reach backend — is it running?'))
  }, [])

  return (
    <div style={{ fontFamily: 'sans-serif', padding: '2rem' }}>
      <h1>Summer Lease</h1>
      <p>Backend says: <strong>{message}</strong></p>
    </div>
  )
}

export default App
