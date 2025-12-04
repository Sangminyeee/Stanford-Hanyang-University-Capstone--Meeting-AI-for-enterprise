import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/common/Card";

export default function ProjectsPage() {
  return (
    <div className="flex flex-col gap-8">
      <PageHeader title="Projects" />
      <Card className="p-6">
        <p className="text-slate-600">Projects 페이지입니다.</p>
      </Card>
    </div>
  );
}

