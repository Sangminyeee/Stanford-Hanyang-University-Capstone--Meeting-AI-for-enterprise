"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card } from "@/components/common/Card";
import { Button } from "@/components/common/Button";
import { Badge } from "@/components/common/Badge";

export default function CreateMeetingPage() {
  const router = useRouter();
  const [formData, setFormData] = useState({
    title: "Marketing Strategy Review",
    date: "Nov 30",
    startTime: "9:00 AM",
    endTime: "11:00 AM",
    attendees: ["Kim minsoo", "Park minsoo", "Lee minsoo"],
    project: "Project A",
    tags: ["Design", "PM"],
    status: "Scheduled",
    purpose: "",
    attachments: [] as File[],
  });

  const [newAttendee, setNewAttendee] = useState("");
  const [newTag, setNewTag] = useState("");

  const handleAddAttendee = () => {
    if (newAttendee.trim() && !formData.attendees.includes(newAttendee.trim())) {
      setFormData({
        ...formData,
        attendees: [...formData.attendees, newAttendee.trim()],
      });
      setNewAttendee("");
    }
  };

  const handleRemoveAttendee = (attendee: string) => {
    setFormData({
      ...formData,
      attendees: formData.attendees.filter((a) => a !== attendee),
    });
  };

  const handleAddTag = () => {
    if (newTag.trim() && !formData.tags.includes(newTag.trim())) {
      setFormData({
        ...formData,
        tags: [...formData.tags, newTag.trim()],
      });
      setNewTag("");
    }
  };

  const handleRemoveTag = (tag: string) => {
    setFormData({
      ...formData,
      tags: formData.tags.filter((t) => t !== tag),
    });
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFormData({
        ...formData,
        attachments: [...formData.attachments, ...Array.from(e.target.files)],
      });
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // TODO: API 호출로 회의 생성
    console.log("Meeting created:", formData);
    router.push("/meetings");
  };

  const handleCancel = () => {
    router.push("/meetings");
  };

  return (
    <div className="flex flex-col gap-8">
      <h1 className="text-2xl font-bold text-slate-900">Create new meeting</h1>

      <form onSubmit={handleSubmit} className="flex flex-col gap-6">
        {/* Meeting Details Card */}
        <Card className="p-6">
          <div className="flex flex-col gap-6">
            {/* Title */}
            <div>
              <input
                type="text"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                className="text-2xl font-bold text-slate-900 w-full border-none outline-none bg-transparent"
                placeholder="Meeting Title"
              />
            </div>

            {/* Details Grid */}
            <div className="grid grid-cols-2 gap-6">
              {/* Date */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Date
                </label>
                <input
                  type="text"
                  value={formData.date}
                  onChange={(e) => setFormData({ ...formData, date: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Nov 30"
                />
              </div>

              {/* Time */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Time
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    value={formData.startTime}
                    onChange={(e) => setFormData({ ...formData, startTime: e.target.value })}
                    className="flex-1 px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="9:00 AM"
                  />
                  <span className="text-slate-500">-</span>
                  <input
                    type="text"
                    value={formData.endTime}
                    onChange={(e) => setFormData({ ...formData, endTime: e.target.value })}
                    className="flex-1 px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="11:00 AM"
                  />
                </div>
              </div>

              {/* Attendees */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Attendees
                </label>
                <div className="flex flex-wrap gap-2 mb-2">
                  {formData.attendees.map((attendee) => (
                    <div
                      key={attendee}
                      className="flex items-center gap-2 px-3 py-1.5 bg-slate-50 rounded-full text-sm text-slate-700"
                    >
                      <div className="w-5 h-5 bg-slate-300 rounded-full"></div>
                      <span>{attendee}</span>
                      <button
                        type="button"
                        onClick={() => handleRemoveAttendee(attendee)}
                        className="text-slate-400 hover:text-slate-600"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={newAttendee}
                    onChange={(e) => setNewAttendee(e.target.value)}
                    onKeyPress={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        handleAddAttendee();
                      }
                    }}
                    className="flex-1 px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Add attendee"
                  />
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={handleAddAttendee}
                  >
                    Add
                  </Button>
                </div>
              </div>

              {/* Project */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Project
                </label>
                <select
                  value={formData.project}
                  onChange={(e) => setFormData({ ...formData, project: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option>Project A</option>
                  <option>Project B</option>
                  <option>Project C</option>
                </select>
              </div>

              {/* Tags */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Tag
                </label>
                <div className="flex flex-wrap gap-2 mb-2">
                  {formData.tags.map((tag) => (
                    <div key={tag} className="flex items-center gap-1">
                      <Badge
                        variant="tag"
                        className={
                          tag === "Design"
                            ? "bg-blue-50 text-blue-700"
                            : "bg-slate-100 text-slate-700"
                        }
                      >
                        {tag}
                      </Badge>
                      <button
                        type="button"
                        onClick={() => handleRemoveTag(tag)}
                        className="text-slate-400 hover:text-slate-600 ml-1"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={newTag}
                    onChange={(e) => setNewTag(e.target.value)}
                    onKeyPress={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        handleAddTag();
                      }
                    }}
                    className="flex-1 px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Add tag"
                  />
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={handleAddTag}
                  >
                    Add
                  </Button>
                </div>
              </div>

              {/* Status */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  Status
                </label>
                <select
                  value={formData.status}
                  onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option>Scheduled</option>
                  <option>In Progress</option>
                  <option>Completed</option>
                </select>
              </div>
            </div>
          </div>
        </Card>

        {/* Purpose & Background Card */}
        <Card className="p-6">
          <div className="flex flex-col gap-4">
            <h2 className="text-lg font-semibold text-slate-900">
              Purpose & Background
            </h2>
            <p className="text-sm text-slate-600">
              이번 회의에서 의논할 안건, 회의 진행 배경, 목표 등 회의에 대한 내용을 자유롭게 작성해주세요. AI가 이를 토대로 회의 준비를 도와줍니다.
            </p>
            <textarea
              value={formData.purpose}
              onChange={(e) => setFormData({ ...formData, purpose: e.target.value })}
              className="w-full px-4 py-3 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[120px] resize-y"
              placeholder="회의 목적과 배경을 작성해주세요..."
            />
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <svg
                className="w-5 h-5"
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
              <label className="cursor-pointer hover:text-slate-800">
                <input
                  type="file"
                  multiple
                  onChange={handleFileChange}
                  className="hidden"
                />
                회의 관련 자료를 첨부해주세요
              </label>
              {formData.attachments.length > 0 && (
                <span className="text-blue-600">
                  ({formData.attachments.length}개 파일)
                </span>
              )}
            </div>
          </div>
        </Card>

        {/* Related Meeting Import Card */}
        <Card className="p-6">
          <div className="flex flex-col gap-4">
            <h2 className="text-lg font-semibold text-slate-900">
              관련 회의 불러오기
            </h2>
            <p className="text-sm text-slate-600">
              이전 회의록을 불러오면, 그 내용을 토대로 초안을 만들어드려요.
            </p>
            <Button type="button" variant="secondary" size="md" className="w-fit">
              불러오기
            </Button>
          </div>
        </Card>

        {/* Action Buttons */}
        <div className="flex justify-end gap-3">
          <Button type="button" variant="secondary" onClick={handleCancel}>
            취소
          </Button>
          <Button type="submit" variant="primary">
            완성
          </Button>
        </div>
      </form>
    </div>
  );
}

