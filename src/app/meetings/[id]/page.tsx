"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { MeetingTabs } from "@/components/meetings/MeetingTabs";
import { MeetingOverviewSection } from "@/components/meetings/MeetingOverviewSection";
import { MeetingPrepSection } from "@/components/meetings/MeetingPrepSection";
import { MeetingOutcomesSection } from "@/components/meetings/MeetingOutcomesSection";

type TabType = "overview" | "prep" | "live" | "outcomes" | "patterns";

export default function MeetingDetailPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabType>("overview");
  const [isEditMode, setIsEditMode] = useState(false);
  const [meetingData, setMeetingData] = useState({
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
  });

  const handleCancel = () => {
    setIsEditMode(false);
    // TODO: 원래 데이터로 복원
  };

  const handleAIEdit = () => {
    // TODO: AI 수정 기능 구현
    console.log("AI Edit clicked");
  };

  const handleComplete = () => {
    // TODO: API 호출로 회의 정보 저장
    console.log("Meeting updated:", meetingData);
    setIsEditMode(false);
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case "overview":
        return (
          <MeetingOverviewSection
            isEditMode={isEditMode}
            meetingData={meetingData}
            onMeetingDataChange={setMeetingData}
            onEditModeChange={setIsEditMode}
          />
        );
      case "prep":
        return (
          <MeetingPrepSection
            isEditMode={isEditMode}
            meetingData={meetingData}
            onMeetingDataChange={setMeetingData}
            onEditModeChange={setIsEditMode}
          />
        );
      case "live":
        return (
          <Card className="p-12 text-center">
            <p className="text-slate-500">Live view coming soon</p>
          </Card>
        );
      case "outcomes":
        return <MeetingOutcomesSection />;
      case "patterns":
        return (
          <Card className="p-12 text-center">
            <p className="text-slate-500">Pattern analysis coming soon</p>
          </Card>
        );
      default:
        return (
          <MeetingOverviewSection
            isEditMode={isEditMode}
            meetingData={meetingData}
            onMeetingDataChange={setMeetingData}
            onEditModeChange={setIsEditMode}
          />
        );
    }
  };

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        title="Meetings"
        action={
          isEditMode ? (
            <div className="flex items-center gap-3">
              <Button variant="secondary" size="md" onClick={handleCancel}>
                취소
              </Button>
              <Button variant="ghost" size="md" onClick={handleAIEdit} className="bg-blue-50 text-blue-600 hover:bg-blue-100">
                AI 수정
              </Button>
              <Button variant="primary" size="md" onClick={handleComplete}>
                완성
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <Button variant="primary" size="md" onClick={() => router.push("/meetings/new")}>
                + New Meeting
              </Button>
              {(activeTab === "overview" || activeTab === "prep") && (
                <Button variant="secondary" size="md" onClick={() => setIsEditMode(true)}>
                  편집
                </Button>
              )}
            </div>
          )
        }
      />
      
      <Card className="p-0">
        <div className="p-6">
          <MeetingTabs activeTab={activeTab} onTabChange={setActiveTab} />
        </div>
        <div className="px-6 pb-6">
          {renderTabContent()}
        </div>
      </Card>
    </div>
  );
}

