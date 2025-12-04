import { PageHeader } from "@/components/layout/PageHeader";
import { TodayMeetingsCard } from "@/components/dashboard/TodayMeetingsCard";
import { ActionItemsCard } from "@/components/dashboard/ActionItemsCard";
import { RecentMeetingsCard } from "@/components/dashboard/RecentMeetingsCard";

export default function DashboardPage() {
  return (
    <div className="flex flex-col gap-10">
      <PageHeader title="Dashboard" />

      {/* Today's Meetings + My Action Items */}
      <div className="grid grid-cols-2 gap-6">
        <TodayMeetingsCard />
        <ActionItemsCard />
      </div>

      {/* Recent Meetings */}
      <RecentMeetingsCard />
    </div>
  );
}
