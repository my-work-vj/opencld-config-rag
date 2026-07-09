import { BrowserRouter, Navigate, Routes, Route, useParams } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppShell } from '@/components/layout/AppShell'
import { WelcomePage } from '@/pages/WelcomePage'
import { CollectionsPage } from '@/pages/CollectionsPage'
import { CollectionDetailPage } from '@/pages/CollectionDetailPage'
import { INDEX_PROFILES_PATH } from '@/lib/terminology'
import { DataSourcesPage } from '@/pages/DataSourcesPage'
import { DataSourceDetailPage } from '@/pages/DataSourceDetailPage'
import { KnowledgeBasesPage } from '@/pages/KnowledgeBasesPage'
import { KnowledgeBaseDetailPage } from '@/pages/KnowledgeBaseDetailPage'
import EvaluationDashboardPage from '@/pages/EvaluationDashboardPage'
import CollectionEvaluationPage from '@/pages/CollectionEvaluationPage'

function LegacyCollectionRedirect() {
  const { name } = useParams<{ name: string }>()
  if (name) {
    return <Navigate to={`${INDEX_PROFILES_PATH}/${encodeURIComponent(name)}`} replace />
  }
  return <Navigate to={INDEX_PROFILES_PATH} replace />
}

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
      <BrowserRouter basename="/ingestion">
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<WelcomePage />} />
            <Route path="data-sources" element={<DataSourcesPage />} />
            <Route path="data-sources/:id" element={<DataSourceDetailPage />} />
            <Route path="index-profiles" element={<CollectionsPage />} />
            <Route path="index-profiles/:name" element={<CollectionDetailPage />} />
            <Route path="collections" element={<LegacyCollectionRedirect />} />
            <Route path="collections/:name" element={<LegacyCollectionRedirect />} />
            <Route path="evaluation" element={<EvaluationDashboardPage />} />
            <Route path="evaluation/:name" element={<CollectionEvaluationPage />} />
            <Route path="knowledge-bases" element={<KnowledgeBasesPage />} />
            <Route path="knowledge-bases/:name" element={<KnowledgeBaseDetailPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
