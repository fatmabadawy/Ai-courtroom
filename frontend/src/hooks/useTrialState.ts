import { useQuery } from '../shims/reactQuery'
import { trialApi } from '../api/client'
import type { TrialStateResponse } from '../types/schemas'

export function useTrialState(caseId: string, enabled = true) {
  return useQuery<TrialStateResponse>({
    queryKey: ['trial', caseId],
    queryFn: () => trialApi.getState(caseId),
    enabled: enabled && !!caseId,
    refetchInterval: (query: any) => {
      const status = query.state.data?.status
      return status === 'running' || status === 'pending' ? 3000 : false
    },
  })
}
