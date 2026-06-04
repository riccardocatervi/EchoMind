import { useQuery } from "@tanstack/react-query";

import { getMyProfile } from "@/api/profile";
import { queryKeys } from "@/hooks/queryKeys";

export function useProfile() {
  return useQuery({
    queryKey: queryKeys.profile,
    queryFn: getMyProfile,
  });
}
