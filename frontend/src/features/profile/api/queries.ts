import { useQuery } from "@tanstack/react-query";

import { profileKeys } from "@/features/profile/api/keys";
import { getMyProfile } from "@/features/profile/api/requests";

export function useProfile() {
  return useQuery({
    queryKey: profileKeys.me,
    queryFn: getMyProfile,
  });
}
