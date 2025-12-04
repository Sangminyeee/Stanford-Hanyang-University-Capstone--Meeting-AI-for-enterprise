import { Card } from "@/components/common/Card";
import { Button } from "@/components/common/Button";
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

export function MeetingOverviewSection() {
  return (
    <div className="space-y-6">
      <MeetingHeader {...meetingData} />

      {/* Purpose */}
      <Card className="p-6">
        <h2 className="text-xl font-semibold text-slate-900 mb-4">Purpose</h2>
        <p className="text-sm text-slate-600 leading-relaxed">
          Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod
          tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim
          veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex
          ea commodo consequat. Duis aute irure dolor in reprehenderit in
          voluptate velit esse cillum dolore eu fugiat nulla pariatur.
        </p>
      </Card>

      {/* Action Cards */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="p-5">
          <h3 className="text-base font-semibold text-slate-900 mb-2">Prep</h3>
          <p className="text-sm text-slate-600 mb-4">
            AI-generated prep is ready
          </p>
          <Button variant="secondary" size="sm" className="w-full">
            View Prep Summary
          </Button>
        </Card>
        <Card className="p-5">
          <h3 className="text-base font-semibold text-slate-900 mb-2">Live</h3>
          <p className="text-sm text-slate-600 mb-4">
            Ready to start meeting?
          </p>
          <Button variant="secondary" size="sm" className="w-full">
            Enter Live
          </Button>
        </Card>
        <Card className="p-5">
          <h3 className="text-base font-semibold text-slate-900 mb-2">
            Outcomes
          </h3>
          <p className="text-sm text-slate-600 mb-4">
            Not started yet
          </p>
          <Button variant="secondary" size="sm" className="w-full">
            View Minutes
          </Button>
        </Card>
      </div>
    </div>
  );
}

