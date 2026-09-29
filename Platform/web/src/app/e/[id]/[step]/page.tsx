"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { STEPS, StepKey } from "@/lib/steps";
import { useEng } from "@/components/engagement";
import { Card, PageTitle } from "@/components/ui";
import { ConsentStep, QuestionnaireStep, BrandStep } from "@/components/steps-a";
import { DataStep, SummaryStep, IssuesStep } from "@/components/steps-b";
import { KpisStep, SegmentsStep, BuildStep } from "@/components/steps-c";
import { ReviewStep, AcceptStep, PublishStep } from "@/components/steps-d";

const VIEWS: Record<StepKey, () => React.ReactNode> = {
  consent: ConsentStep, questionnaire: QuestionnaireStep, brand: BrandStep, data: DataStep, summary: SummaryStep, issues: IssuesStep,
  kpis: KpisStep, segments: SegmentsStep, build: BuildStep, review: ReviewStep, accept: AcceptStep, publish: PublishStep,
};

export default function StepPage() {
  const { step } = useParams<{ step: string }>();
  const { id, data } = useEng();
  const meta = STEPS.find((s) => s.key === step);
  if (!data) return null;
  if (!meta) return <Card><PageTitle title="We could not find that step" /><Link href={`/e/${id}`} className="text-primary underline">Back to your progress</Link></Card>;
  if (data.statuses[meta.key] === "locked") {
    const prev = STEPS[meta.n - 2];
    return (
      <>
        <PageTitle eyebrow={`Step ${meta.n}`} title={meta.title} />
        <Card><h2 className="font-semibold">This step is locked</h2><p className="text-muted mt-1">Finish step {prev.n}, {prev.title}, first. Steps run in order so nothing is skipped.</p>
          <Link href={`/e/${id}/${prev.key}`} className="inline-flex mt-4 items-center rounded-xl bg-primary text-on-primary px-5 min-h-11 font-semibold hover:bg-primary-hover">Go to step {prev.n}</Link></Card>
      </>
    );
  }
  const View = VIEWS[meta.key];
  return <View />;
}
