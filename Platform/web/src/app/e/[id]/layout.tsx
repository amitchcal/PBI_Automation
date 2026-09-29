import { EngagementProvider } from "@/components/engagement";
import { Shell } from "@/components/shell";

export default async function EngagementLayout({ children, params }: { children: React.ReactNode; params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <EngagementProvider id={id}>
      <Shell>{children}</Shell>
    </EngagementProvider>
  );
}
