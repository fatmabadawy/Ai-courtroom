import { useQuery } from '../shims/reactQuery'
import { evidenceApi } from '../api/client'
import type { EvidenceGraphResponse } from '../types/schemas'

export function useEvidenceGraph(caseId: string) {
  return useQuery<EvidenceGraphResponse>({
    queryKey: ['evidence-graph', caseId],
    queryFn: () => evidenceApi.graph(caseId),
    enabled: !!caseId,
  })
}
