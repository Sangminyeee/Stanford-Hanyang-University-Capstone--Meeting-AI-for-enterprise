import { Card } from "@/components/common/Card";
import { Button } from "@/components/common/Button";
import { Badge } from "@/components/common/Badge";
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

const materials = [
  {
    id: 1,
    title: "Lorem ipsum",
    description: "Lorem ipsum dolor sit amet consectetur.",
    iconColor: "bg-blue-100",
    iconTextColor: "text-blue-600",
  },
  {
    id: 2,
    title: "Lorem ipsum",
    description: "Lorem ipsum dolor sit amet consectetur.",
    iconColor: "bg-yellow-100",
    iconTextColor: "text-yellow-600",
  },
  {
    id: 3,
    title: "Lorem ipsum",
    description: "Lorem ipsum dolor sit amet consectetur.",
    iconColor: "bg-green-100",
    iconTextColor: "text-green-600",
  },
];

const agendaItems = [
  {
    id: 1,
    title: "Review wireframes",
    description: "Validate latest wireframe revisions",
    duration: "20min",
  },
  {
    id: 2,
    title: "Discuss design",
    description: "Finalize UI, colors, layouts, etc.",
    duration: "20min",
  },
  {
    id: 3,
    title: "Outline next steps",
    description: "Assign tasks and responsibilities",
    duration: "20min",
  },
];

const briefings = [
  { role: "PM", text: "Lorem ipsum dolor sit amet consectetur." },
  { role: "Designer", text: "Lorem ipsum dolor sit amet consectetur." },
];

export function MeetingPrepSection() {
  return (
    <div className="space-y-6">
      <MeetingHeader {...meetingData} />

      {/* Purpose & Background */}
      <Card className="p-6">
        <h2 className="text-xl font-semibold text-slate-900 mb-4">
          Purpose & Background
        </h2>
        <p className="text-sm text-slate-600 leading-relaxed mb-4">
          Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do
          eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim
          ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut
          aliquip ex ea commodo consequat. Duis aute irure dolor in
          reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla
          pariatur.
        </p>
        <div className="flex gap-3">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center">
              <span className="text-blue-600 text-sm">📄</span>
            </div>
            <span className="text-sm text-slate-600">Lorem ipsum</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-yellow-100 rounded-lg flex items-center justify-center">
              <span className="text-yellow-600 text-sm">📄</span>
            </div>
            <span className="text-sm text-slate-600">Lorem ipsum</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-green-100 rounded-lg flex items-center justify-center">
              <span className="text-green-600 text-sm">📄</span>
            </div>
            <span className="text-sm text-slate-600">Lorem ipsum</span>
          </div>
        </div>
      </Card>

      {/* Material Summary */}
      <Card className="p-6">
        <h2 className="text-xl font-semibold text-slate-900 mb-4">
          Material Summary
        </h2>
        <div className="grid grid-cols-3 gap-4">
          {materials.map((material) => (
            <div
              key={material.id}
              className="p-4 bg-slate-50 rounded-lg border border-slate-100"
            >
              <div className={`w-10 h-10 ${material.iconColor} rounded-lg flex items-center justify-center mb-3`}>
                <span className={`${material.iconTextColor} text-lg`}>📄</span>
              </div>
              <h3 className="font-semibold text-slate-900 text-sm mb-1">
                {material.title}
              </h3>
              <p className="text-xs text-slate-600">{material.description}</p>
            </div>
          ))}
        </div>
      </Card>

      {/* Recommended Agenda */}
      <Card className="p-6">
        <h2 className="text-xl font-semibold text-slate-900 mb-4">
          Recommended Agenda
        </h2>
        <div className="grid grid-cols-3 gap-4">
          {agendaItems.map((item) => (
            <div
              key={item.id}
              className="p-4 bg-white rounded-lg border border-slate-100"
            >
              <h3 className="font-semibold text-slate-900 text-sm mb-2">
                {item.title}
              </h3>
              <p className="text-xs text-slate-600 mb-3">{item.description}</p>
              <div className="text-xs text-slate-500">{item.duration}</div>
            </div>
          ))}
        </div>
      </Card>

      {/* Briefings by Attendees */}
      <Card className="p-6">
        <h2 className="text-xl font-semibold text-slate-900 mb-4">
          Briefings by Attendees
        </h2>
        <div className="space-y-3">
          {briefings.map((briefing, idx) => (
            <div key={idx} className="flex items-center gap-3">
              <Badge variant="tag">{briefing.role}</Badge>
              <span className="text-sm text-slate-600">{briefing.text}</span>
            </div>
          ))}
        </div>
      </Card>

      {/* Mark as Prepared Button */}
      <div className="flex justify-end">
        <Button variant="primary" size="md">
          Mark as Prepared
        </Button>
      </div>
    </div>
  );
}

