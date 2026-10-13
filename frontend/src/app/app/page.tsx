import { Suspense } from "react";
import { Workspace } from "@/components/workspace";

export default function AppPage() {
  return (
    <Suspense fallback={<p className="p-8 text-muted">Opening the library…</p>}>
      <Workspace />
    </Suspense>
  );
}
