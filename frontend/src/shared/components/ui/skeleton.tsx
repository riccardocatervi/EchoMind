import type { ComponentProps } from "react";

import { cn } from "@/shared/lib/utils";

function Skeleton({ className, ...props }: ComponentProps<"div">) {
  return <div className={cn("animate-pulse rounded-md bg-muted", className)} {...props} />;
}

export { Skeleton };
