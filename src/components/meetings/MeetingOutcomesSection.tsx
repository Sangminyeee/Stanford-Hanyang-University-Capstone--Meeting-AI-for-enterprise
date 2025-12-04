import { Card } from "@/components/common/Card";
import { MeetingHeader } from "./MeetingHeader";

const meetingData = {
  title: "Marketing Strategy Review",
  date: "Nov 30",
  time: "9:00 AM",
  endTime: "11:00 AM",
  duration: "2h",
  attendees: ["Kim minsoo", "Park minsoo", "Lee minsoo"],
  project: "Project A",
  tags: ["Design", "PM"],
  status: "Scheduled",
};

export function MeetingOutcomesSection() {
  return (
    <div className="space-y-6">
      <MeetingHeader {...meetingData} />

      {/* One-page Summary */}
      <Card className="p-6">
        <h2 className="text-xl font-semibold text-slate-900 mb-4">
          One-page Summary
        </h2>
        <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 relative">
          <div className="flex items-start gap-4 mb-4">
            <div className="w-24 text-sm font-semibold text-slate-900">
              Purpose
            </div>
            <div className="flex-1 text-sm text-slate-600">
              Review and finalize the marketing strategy for Q4, including
              budget allocation, campaign planning, and performance metrics
              analysis.
            </div>
          </div>
          <div className="absolute bottom-4 right-4 text-xs text-slate-500">
            20min
          </div>
        </div>
      </Card>
    </div>
  );
}

