import { api } from "@/shared/api/axios";
import {
  profileReadSchema,
  type ProfileRead,
  type ProfileUpdate,
} from "@/features/profile/schemas/profile";

export async function getMyProfile(): Promise<ProfileRead> {
  const { data } = await api.get("/profiles/me");
  return profileReadSchema.parse(data);
}

export async function updateMyProfile(payload: ProfileUpdate): Promise<ProfileRead> {
  const { data } = await api.patch("/profiles/me", payload);
  return profileReadSchema.parse(data);
}
