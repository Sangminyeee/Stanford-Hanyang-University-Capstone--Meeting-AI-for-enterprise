"use client";

import { useState } from "react";
import { Card } from "@/components/common/Card";
import { Button } from "@/components/common/Button";
import { Badge } from "@/components/common/Badge";
import { MeetingHeader } from "./MeetingHeader";
import { EditableMeetingHeader } from "./EditableMeetingHeader";

interface MeetingPrepSectionProps {
  isEditMode?: boolean;
  meetingData?: {
    title: string;
    date: string;
    time: string;
    endTime?: string;
    duration: string;
    attendees: string[];
    project: string;
    tags: string[];
    status: string;
  };
  onMeetingDataChange?: (data: any) => void;
  onEditModeChange?: (isEdit: boolean) => void;
}

const defaultMeetingData = {
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

const defaultMaterials = [
  {
    id: 1,
    title: "Key Flows",
    description: "user journeys in the current wireframes.",
    iconColor: "bg-blue-100",
    iconTextColor: "text-blue-600",
    fileName: "Key Flows",
  },
  {
    id: 2,
    title: "Next Steps, Priorities & Timeline",
    description: "Agreed action items, their priority",
    iconColor: "bg-yellow-100",
    iconTextColor: "text-yellow-600",
    fileName: "Next Steps, Priorities & Timeline",
  },
  {
    id: 3,
    title: "Design Feedback & Discussion Points",
    description: "Key comments, issues, and ideas",
    iconColor: "bg-green-100",
    iconTextColor: "text-green-600",
    fileName: "Design Feedback & Discussion Points",
  },
];

const defaultAgendaItems = [
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

const defaultBriefings = [
  { role: "PM", text: "briefly share project goals, timeline, and key decisions" },
  { role: "Designer", text: "walk through the main wireframes and highlight major design considerations" },
];

export function MeetingPrepSection({
  isEditMode = false,
  meetingData = defaultMeetingData,
  onMeetingDataChange,
  onEditModeChange,
}: MeetingPrepSectionProps) {
  const [purpose, setPurpose] = useState(
    "The purpose is to evaluate how effectively our current strategies support our overall business goals, while identifying strengths, weaknesses, and gaps across key marketing channels. By examining market and customer responses based on data and performance indicators, this review seeks to clarify what is working well and what needs improvement. Ultimately, it aims to generate clear insights and actionable recommendations to refine and enhance our future marketing direction."
  );
  const [attachments, setAttachments] = useState(defaultMaterials);
  const [materials, setMaterials] = useState(defaultMaterials);
  const [agendaItems, setAgendaItems] = useState(defaultAgendaItems);
  const [briefings, setBriefings] = useState(defaultBriefings);

  const handleFileAdd = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const newFile = e.target.files[0];
      const colorOptions = [
        { iconColor: "bg-blue-100", iconTextColor: "text-blue-600" },
        { iconColor: "bg-yellow-100", iconTextColor: "text-yellow-600" },
        { iconColor: "bg-green-100", iconTextColor: "text-green-600" },
      ];
      const colorIndex = attachments.length % colorOptions.length;
      const newAttachment = {
        id: Date.now(),
        title: newFile.name.replace(/\.[^/.]+$/, ""),
        description: "",
        ...colorOptions[colorIndex],
        fileName: newFile.name,
      };
      setAttachments([...attachments, newAttachment]);
    }
  };

  const handleFileRemove = (id: number) => {
    setAttachments(attachments.filter((att) => att.id !== id));
  };

  const handleMaterialChange = (id: number, field: string, value: string) => {
    setMaterials(
      materials.map((mat) =>
        mat.id === id ? { ...mat, [field]: value } : mat
      )
    );
  };

  const handleAgendaChange = (id: number, field: string, value: string) => {
    setAgendaItems(
      agendaItems.map((item) =>
        item.id === id ? { ...item, [field]: value } : item
      )
    );
  };

  const handleBriefingChange = (index: number, field: string, value: string) => {
    setBriefings(
      briefings.map((brief, idx) =>
        idx === index ? { ...brief, [field]: value } : brief
      )
    );
  };
  return (
    <div className="space-y-6">
      {isEditMode ? (
        <EditableMeetingHeader
          meetingData={meetingData}
          onMeetingDataChange={onMeetingDataChange}
        />
      ) : (
        <MeetingHeader {...meetingData} />
      )}

      {/* Purpose & Background */}
      <Card className="p-6">
        <h2 className="text-xl font-semibold text-slate-900 mb-4">
          Purpose & Background
        </h2>
        {isEditMode ? (
          <>
            <textarea
              value={purpose}
              onChange={(e) => setPurpose(e.target.value)}
              className="w-full px-4 py-3 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[120px] resize-y text-slate-600 leading-relaxed mb-4"
              placeholder="회의 목적과 배경을 작성해주세요..."
            />
            <div className="flex flex-wrap items-center gap-2">
              {attachments.map((attachment) => (
                <div
                  key={attachment.id}
                  className="flex items-center gap-2 px-3 py-1.5 bg-slate-50 rounded-lg border border-slate-200"
                >
                  <div className={`w-6 h-6 ${attachment.iconColor} rounded flex items-center justify-center`}>
                    <svg
                      className={`w-4 h-4 ${attachment.iconTextColor}`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                      />
                    </svg>
                  </div>
                  <span className="text-sm text-slate-700">{attachment.fileName}</span>
                  <button
                    type="button"
                    onClick={() => handleFileRemove(attachment.id)}
                    className="text-slate-400 hover:text-slate-600 ml-1"
                  >
                    ×
                  </button>
                </div>
              ))}
              <label className="flex items-center justify-center w-8 h-8 bg-slate-100 rounded-lg cursor-pointer hover:bg-slate-200 transition-colors">
                <input
                  type="file"
                  onChange={handleFileAdd}
                  className="hidden"
                />
                <span className="text-slate-600 text-lg">+</span>
              </label>
            </div>
          </>
        ) : (
          <>
            <p className="text-sm text-slate-600 leading-relaxed mb-4">
              {purpose}
            </p>
            <div className="flex flex-wrap gap-2">
              {attachments.map((attachment) => (
                <div
                  key={attachment.id}
                  className="flex items-center gap-2 px-3 py-1.5 bg-slate-50 rounded-lg border border-slate-200"
                >
                  <div className={`w-6 h-6 ${attachment.iconColor} rounded flex items-center justify-center`}>
                    <svg
                      className={`w-4 h-4 ${attachment.iconTextColor}`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                      />
                    </svg>
                  </div>
                  <span className="text-sm text-slate-700">{attachment.fileName}</span>
                </div>
              ))}
            </div>
          </>
        )}
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
                <svg
                  className={`w-6 h-6 ${material.iconTextColor}`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
              </div>
              {isEditMode ? (
                <>
                  <input
                    type="text"
                    value={material.title}
                    onChange={(e) => handleMaterialChange(material.id, "title", e.target.value)}
                    className="w-full font-semibold text-slate-900 text-sm mb-1 px-2 py-1 border border-slate-200 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                    placeholder="Title"
                  />
                  <textarea
                    value={material.description}
                    onChange={(e) => handleMaterialChange(material.id, "description", e.target.value)}
                    className="w-full text-xs text-slate-600 px-2 py-1 border border-slate-200 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white resize-none"
                    placeholder="Description"
                    rows={2}
                  />
                </>
              ) : (
                <>
                  <h3 className="font-semibold text-slate-900 text-sm mb-1">
                    {material.title}
                  </h3>
                  <p className="text-xs text-slate-600">{material.description}</p>
                </>
              )}
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
              {isEditMode ? (
                <>
                  <input
                    type="text"
                    value={item.title}
                    onChange={(e) => handleAgendaChange(item.id, "title", e.target.value)}
                    className="w-full font-semibold text-slate-900 text-sm mb-2 px-2 py-1 border border-slate-200 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Title"
                  />
                  <textarea
                    value={item.description}
                    onChange={(e) => handleAgendaChange(item.id, "description", e.target.value)}
                    className="w-full text-xs text-slate-600 mb-3 px-2 py-1 border border-slate-200 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                    placeholder="Description"
                    rows={2}
                  />
                  <input
                    type="text"
                    value={item.duration}
                    onChange={(e) => handleAgendaChange(item.id, "duration", e.target.value)}
                    className="w-full text-xs text-slate-500 px-2 py-1 border border-slate-200 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Duration"
                  />
                </>
              ) : (
                <>
                  <h3 className="font-semibold text-slate-900 text-sm mb-2">
                    {item.title}
                  </h3>
                  <p className="text-xs text-slate-600 mb-3">{item.description}</p>
                  <div className="text-xs text-slate-500">{item.duration}</div>
                </>
              )}
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
            <div key={idx} className="flex items-start gap-3">
              <Badge variant="tag" className="mt-0.5">{briefing.role}</Badge>
              {isEditMode ? (
                <textarea
                  value={briefing.text}
                  onChange={(e) => handleBriefingChange(idx, "text", e.target.value)}
                  className="flex-1 text-sm text-slate-600 px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                  placeholder="Briefing content"
                  rows={2}
                />
              ) : (
                <span className="text-sm text-slate-600 flex-1">{briefing.text}</span>
              )}
            </div>
          ))}
        </div>
      </Card>

      {/* Mark as Prepared Button */}
      {!isEditMode && (
        <div className="flex justify-end">
          <Button variant="primary" size="md">
            Mark as Prepared
          </Button>
        </div>
      )}
    </div>
  );
}

