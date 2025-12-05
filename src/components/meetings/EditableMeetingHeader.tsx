"use client";

import { useState } from "react";
import { Badge } from "@/components/common/Badge";
import { Button } from "@/components/common/Button";

interface EditableMeetingHeaderProps {
  meetingData: {
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
}

export function EditableMeetingHeader({
  meetingData,
  onMeetingDataChange,
}: EditableMeetingHeaderProps) {
  const [localData, setLocalData] = useState(meetingData);
  const [newAttendee, setNewAttendee] = useState("");
  const [newTag, setNewTag] = useState("");

  const updateData = (updates: Partial<typeof meetingData>) => {
    const updated = { ...localData, ...updates };
    setLocalData(updated);
    if (onMeetingDataChange) {
      onMeetingDataChange(updated);
    }
  };

  const handleAddAttendee = () => {
    if (newAttendee.trim() && !localData.attendees.includes(newAttendee.trim())) {
      updateData({
        attendees: [...localData.attendees, newAttendee.trim()],
      });
      setNewAttendee("");
    }
  };

  const handleRemoveAttendee = (attendee: string) => {
    updateData({
      attendees: localData.attendees.filter((a) => a !== attendee),
    });
  };

  const handleAddTag = () => {
    if (newTag.trim() && !localData.tags.includes(newTag.trim())) {
      updateData({
        tags: [...localData.tags, newTag.trim()],
      });
      setNewTag("");
    }
  };

  const handleRemoveTag = (tag: string) => {
    updateData({
      tags: localData.tags.filter((t) => t !== tag),
    });
  };

  const getStatusVariant = (status: string) => {
    switch (status) {
      case "Completed":
        return "status-completed";
      case "In Progress":
        return "status-in-progress";
      case "Scheduled":
        return "status-scheduled";
      default:
        return "status-scheduled";
    }
  };

  return (
    <div className="mb-6 pb-6 border-b border-slate-200">
      {/* Title */}
      <input
        type="text"
        value={localData.title}
        onChange={(e) => updateData({ title: e.target.value })}
        className="text-2xl font-semibold text-slate-900 mb-4 w-full border-none outline-none bg-transparent focus:ring-2 focus:ring-blue-500 rounded px-2 -ml-2"
        placeholder="Meeting Title"
      />

      {/* Date and Time */}
      <div className="flex flex-wrap items-center gap-4 text-sm text-slate-600 mb-4">
        <div className="flex items-center gap-2">
          <span className="text-slate-600">Date:</span>
          <input
            type="text"
            value={localData.date}
            onChange={(e) => updateData({ date: e.target.value })}
            className="px-2 py-1 border border-slate-200 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Nov 30"
          />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-slate-600">Time:</span>
          <input
            type="text"
            value={localData.time}
            onChange={(e) => updateData({ time: e.target.value })}
            className="px-2 py-1 border border-slate-200 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 w-24"
            placeholder="9:00 AM"
          />
          <span>-</span>
          <input
            type="text"
            value={localData.endTime || ""}
            onChange={(e) => updateData({ endTime: e.target.value })}
            className="px-2 py-1 border border-slate-200 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 w-24"
            placeholder="11:00 AM"
          />
        </div>
      </div>

      {/* Attendees */}
      <div className="flex flex-wrap items-center gap-4 mb-4">
        <span className="text-sm text-slate-600">Attendees:</span>
        <div className="flex flex-wrap items-center gap-2">
          {localData.attendees.map((attendee) => (
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
              className="px-2 py-1 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 w-32"
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
      </div>

      {/* Project, Tags, Status */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-600">Project:</span>
          <select
            value={localData.project}
            onChange={(e) => updateData({ project: e.target.value })}
            className="px-2 py-1 text-sm border border-slate-200 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option>Project A</option>
            <option>Project B</option>
            <option>Project C</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-600">Tags:</span>
          <div className="flex flex-wrap items-center gap-2">
            {localData.tags.map((tag) => (
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
                className="px-2 py-1 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 w-24"
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
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-600">Status:</span>
          <select
            value={localData.status}
            onChange={(e) => updateData({ status: e.target.value })}
            className="px-2 py-1 text-sm border border-slate-200 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option>Scheduled</option>
            <option>In Progress</option>
            <option>Completed</option>
          </select>
        </div>
      </div>
    </div>
  );
}

