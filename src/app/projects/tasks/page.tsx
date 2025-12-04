import { PageHeader } from "@/components/layout/PageHeader";
import { Card } from "@/components/common/Card";

export default function MyTasksPage() {
  return (
    <div className="flex flex-col gap-8">
      <PageHeader title="My tasks" />
      <Card className="p-6">
        <p className="text-slate-600">My tasks 페이지입니다.</p>
      </Card>
    </div>
  );
}

