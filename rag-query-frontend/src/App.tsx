import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppShell } from '@/components/layout/AppShell'
import { WelcomePage } from '@/pages/WelcomePage'
import { AgentsPage } from '@/pages/AgentsPage'
import { AgentDetailPage } from '@/pages/AgentDetailPage'
import { PromptsPage } from '@/pages/PromptsPage'
import { PromptDetailPage } from '@/pages/PromptDetailPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10000,
      retry: 1,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<WelcomePage />} />
            <Route path="agents" element={<AgentsPage />} />
            <Route path="agents/:name" element={<AgentDetailPage />} />
            <Route path="prompts" element={<PromptsPage />} />
            <Route path="prompts/:id" element={<PromptDetailPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
