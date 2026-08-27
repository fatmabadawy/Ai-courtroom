import { useQuery } from '../shims/reactQuery'
import { casesApi } from '../api/client'
import type { CaseRow } from '../types/schemas'

export function useCase(caseId: string) {
  return useQuery<CaseRow>({
    queryKey: ['case', caseId],
    queryFn: () => casesApi.get(caseId),
    enabled: !!caseId,
  })
}

export function useCases() {
  return useQuery<CaseRow[]>({
    queryKey: ['cases'],
    queryFn: casesApi.list,
  })
}
