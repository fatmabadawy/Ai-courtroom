import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from './shims/reactQuery'
import { Layout } from './components/Layout'
import { Dashboard } from './pages/Dashboard'
import { CaseCreate } from './pages/CaseCreate'
import { CaseDetail } from './pages/CaseDetail'
import { Courtroom } from './pages/Courtroom'
import { EvidenceExplorer } from './pages/EvidenceExplorer'
import { EvidenceGraph } from './pages/EvidenceGraph'
import { TrialReplay } from './pages/TrialReplay'
import { Verdict } from './pages/Verdict'
import { Login } from './pages/Login'
import { Register } from './pages/Register'
import { authApi } from './api/client'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  if (!authApi.isLoggedIn()) {
    return <Navigate to="/login" replace />
  }
  return <Layout>{children}</Layout>
}

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Public Auth Routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Protected Application Routes */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/cases/new"
            element={
              <ProtectedRoute>
                <CaseCreate />
              </ProtectedRoute>
            }
          />
          <Route
            path="/cases/:caseId"
            element={
              <ProtectedRoute>
                <CaseDetail />
              </ProtectedRoute>
            }
          />
          <Route
            path="/cases/:caseId/courtroom"
            element={
              <ProtectedRoute>
                <Courtroom />
              </ProtectedRoute>
            }
          />
          <Route
            path="/cases/:caseId/evidence"
            element={
              <ProtectedRoute>
                <EvidenceExplorer />
              </ProtectedRoute>
            }
          />
          <Route
            path="/cases/:caseId/graph"
            element={
              <ProtectedRoute>
                <EvidenceGraph />
              </ProtectedRoute>
            }
          />
          <Route
            path="/cases/:caseId/replay"
            element={
              <ProtectedRoute>
                <TrialReplay />
              </ProtectedRoute>
            }
          />
          <Route
            path="/cases/:caseId/verdict"
            element={
              <ProtectedRoute>
                <Verdict />
              </ProtectedRoute>
            }
          />

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
