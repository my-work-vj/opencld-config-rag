import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppShell } from '@/components/layout/AppShell'
import { WelcomePage } from '@/pages/WelcomePage'
import { CollectionsPage } from '@/pages/CollectionsPage'
import { CollectionDetailPage } from '@/pages/CollectionDetailPage'
import { DataSourcesPage } from '@/pages/DataSourcesPage'
import { DataSourceDetailPage } from '@/pages/DataSourceDetailPage'
import { KnowledgeBasesPage } from '@/pages/KnowledgeBasesPage'
import { KnowledgeBaseDetailPage } from '@/pages/KnowledgeBaseDetailPage'

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
            <Route path="data-sources" element={<DataSourcesPage />} />
            <Route path="data-sources/:id" element={<DataSourceDetailPage />} />
            <Route path="collections" element={<CollectionsPage />} />
            <Route path="collections/:name" element={<CollectionDetailPage />} />
            <Route path="knowledge-bases" element={<KnowledgeBasesPage />} />
            <Route path="knowledge-bases/:name" element={<KnowledgeBaseDetailPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
