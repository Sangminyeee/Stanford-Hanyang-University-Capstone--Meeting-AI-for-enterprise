"use client";

import { useState } from "react";
import { Card } from "@/components/common/Card";
import { Button } from "@/components/common/Button";
import { MeetingHeader } from "./MeetingHeader";
import { EditableMeetingHeader } from "./EditableMeetingHeader";

interface MeetingOverviewSectionProps {
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
    purpose: string;
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
  purpose: "The purpose is to evaluate how effectively our current strategies support our overall business goals, while identifying strengths, weaknesses, and gaps across key marketing channels. By examining market and customer responses based on data and performance indicators, this review seeks to clarify what is working well and what needs improvement. Ultimately, it aims to generate clear insights and actionable recommendations to refine and enhance our future marketing direction.",
};

export function MeetingOverviewSection({
  isEditMode = false,
  meetingData = defaultMeetingData,
  onMeetingDataChange,
  onEditModeChange,
}: MeetingOverviewSectionProps) {
  const [localPurpose, setLocalPurpose] = useState(meetingData.purpose || defaultMeetingData.purpose);

  const handlePurposeChange = (value: string) => {
    setLocalPurpose(value);
    if (onMeetingDataChange) {
      onMeetingDataChange({
        ...meetingData,
        purpose: value,
      });
    }
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

      {/* Purpose */}
      <Card className="p-6">
        <h2 className="text-xl font-semibold text-slate-900 mb-4">Purpose</h2>
        {isEditMode ? (
          <textarea
            value={localPurpose}
            onChange={(e) => handlePurposeChange(e.target.value)}
            className="w-full px-4 py-3 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[120px] resize-y text-slate-600 leading-relaxed"
            placeholder="회의 목적을 작성해주세요..."
          />
        ) : (
          <p className="text-sm text-slate-600 leading-relaxed">
            {meetingData.purpose || defaultMeetingData.purpose}
          </p>
        )}
      </Card>

      {/* Action Cards */}
      {!isEditMode && (
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
      )}
    </div>
  );
}

