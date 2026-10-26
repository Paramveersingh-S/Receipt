"use client";

import React, { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import {
  Play,
  RotateCcw,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Terminal,
  Filter,
  Flame,
  Search,
} from "lucide-react";
import { SSEEvent } from "@/types";

const STAGES = [
  { id: "intent", name: "1. Intent Extraction", desc: "Parse testable acceptance criteria from PR" },
  { id: "failbefore", name: "2. Fail-Before Proofs", desc: "Run candidate tests on base commit (must FAIL)" },
  { id: "suite", name: "3. Full Regression Suite", desc: "Execute complete suite on head in isolated sandbox" },
  { id: "mutation", name: "4. AST Mutation Testing", desc: "Generate & kill mutants on changed lines only" },
  { id: "scar", name: "5. Scar Tissue Constraints", desc: "Check diffs against repo historical failure lessons" },
  { id: "browser", name: "6. Browser QA", desc: "Verify UI state transitions in headless browser" },
  { id: "receipt", name: "7. Receipt Minting", desc: "Digest evidence & mint signed cryptographic receipt" },
];

const INITIAL_EVENTS: SSEEvent[] = [
  { seq: 1, type: "run_started", at: "12:00:00.120", payload: { run_id: "rc_run_01", repo: "receipt-demo-shop", pr: 12 } },
  { seq: 2, type: "stage_started", at: "12:00:00.450", payload: { stage: "intent", criteria_count: 3 } },
  { seq: 3, type: "intent_extracted", at: "12:00:01.810", payload: { criteria: ["Coupon half-up cents", "400 on expired", "Idempotency key"] } },
  { seq: 4, type: "stage_started", at: "12:00:02.100", payload: { stage: "failbefore", tests: 3 } },
  { seq: 5, type: "test_fail_before_passed", at: "12:00:04.220", payload: { test: "test_coupon_rounds_half_up", result: "FAIL_AS_EXPECTED", vacuous: false } },
  { seq: 6, type: "stage_started", at: "12:00:04.500", payload: { stage: "suite", sandbox: "bwrap-isolated" } },
  { seq: 7, type: "suite_completed", at: "12:00:07.110", payload: { passed: 44, failed: 0, regressions: 0 } },
  { seq: 8, type: "stage_started", at: "12:00:07.400", payload: { stage: "mutation", mutants_total: 36 } },
  { seq: 9, type: "mutant_killed", at: "12:00:09.300", payload: { mutant: "op_comparison_invert_line_48", test: "test_coupon_rounds_half_up" } },
  { seq: 10, type: "mutation_summary", at: "12:00:10.800", payload: { killed: 32, survived: 4, score: 0.89 } },
  { seq: 11, type: "stage_started", at: "12:00:11.100", payload: { stage: "scar", constraints_evaluated: 7 } },
  { seq: 12, type: "constraint_passed", at: "12:00:12.300", payload: { id: "sc_001", rule: "Money is integer cents" } },
  { seq: 13, type: "constraint_passed", at: "12:00:12.550", payload: { id: "sc_002", rule: "Idempotency key required" } },
  { seq: 14, type: "stage_started", at: "12:00:12.800", payload: { stage: "browser", checks: 2 } },
  { seq: 15, type: "browser_check_passed", at: "12:00:14.200", payload: { name: "Coupon updates cart UI", screenshot: "ar_shot_1" } },
  { seq: 16, type: "receipt_minted", at: "12:00:14.950", payload: { verdict: "VERIFIED", score: 92, slug: "x7k2m9" } },
];

export function LivePipelineView() {
  const [isRunning, setIsRunning] = useState(false);
  const [activeStageIndex, setActiveStageIndex] = useState(6); // Completed by default
  const [events, setEvents] = useState<SSEEvent[]>(INITIAL_EVENTS);
  const [filterType, setFilterType] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const terminalRef = useRef<HTMLDivElement>(null);

  // Auto-scroll terminal on new events
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [events]);

  // Simulated live execution replay
  const handleReplayRun = () => {
    setIsRunning(true);
    setEvents([]);
    setActiveStageIndex(0);

    let stageIdx = 0;
    let eventIdx = 0;

    const interval = setInterval(() => {
      if (eventIdx < INITIAL_EVENTS.length) {
        const nextEvt = INITIAL_EVENTS[eventIdx];
        setEvents((prev) => [...prev, nextEvt]);

        if (nextEvt.type === "stage_started") {
          setActiveStageIndex(stageIdx);
          stageIdx = Math.min(stageIdx + 1, STAGES.length - 1);
        }
        eventIdx++;
      } else {
        clearInterval(interval);
        setIsRunning(false);
        setActiveStageIndex(6);
      }
    }, 650);
  };

  const filteredEvents = events.filter((e) => {
    const matchesFilter =
      filterType === "all" ||
      (filterType === "stages" && e.type.includes("stage")) ||
      (filterType === "mutation" && e.type.includes("mutan")) ||
      (filterType === "scar" && e.type.includes("constraint"));

    const matchesSearch =
      searchQuery === "" ||
      e.type.toLowerCase().includes(searchQuery.toLowerCase()) ||
      JSON.stringify(e.payload).toLowerCase().includes(searchQuery.toLowerCase());

    return matchesFilter && matchesSearch;
  });

  return (
    <div className="w-full max-w-5xl mx-auto space-y-6">
      {/* Top Header & Simulation Controls */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 rounded-xl glass-panel">
        <div>
          <h2 className="text-lg font-bold flex items-center gap-2">
            <Flame className="w-5 h-5 text-emerald-400" />
            Verification Sandbox Pipeline
          </h2>
          <p className="text-xs text-gray-400 mt-0.5">
            Real-time multi-stage evidence generation in isolated bubblewrap/docker container.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={handleReplayRun}
            disabled={isRunning}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold font-mono transition-all ${
              isRunning
                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 cursor-not-allowed"
                : "bg-emerald-500 hover:bg-emerald-400 text-black shadow-lg shadow-emerald-500/20"
            }`}
          >
            {isRunning ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>RUNNING VERIFICATION...</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>REPLAY LIVE RUN</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Pipeline Stage Timeline */}
      <div className="p-5 rounded-xl glass-panel space-y-4">
        <div className="flex items-center justify-between text-xs text-gray-400 font-mono">
          <span>PIPELINE EXECUTION PROGRESS</span>
          <span className="text-emerald-400">
            {isRunning ? `STAGE ${activeStageIndex + 1} OF ${STAGES.length}` : "ALL 7 STAGES COMPLETE (14.9s)"}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-7 gap-2">
          {STAGES.map((stg, idx) => {
            const isCompleted = idx < activeStageIndex || (!isRunning && activeStageIndex === 6);
            const isCurrent = isRunning && idx === activeStageIndex;

            return (
              <div
                key={stg.id}
                className={`p-3 rounded-lg border transition-all ${
                  isCurrent
                    ? "bg-emerald-500/10 border-emerald-500/60 shadow-[0_0_15px_rgba(16,185,129,0.2)]"
                    : isCompleted
                    ? "bg-white/5 border-emerald-500/30 text-gray-200"
                    : "bg-black/30 border-white/5 text-gray-500"
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[10px] font-mono font-bold text-gray-400">
                    0{idx + 1}
                  </span>
                  {isCurrent ? (
                    <Loader2 className="w-3.5 h-3.5 text-emerald-400 animate-spin" />
                  ) : isCompleted ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  ) : (
                    <div className="w-2 h-2 rounded-full bg-gray-600" />
                  )}
                </div>

                <div className="font-semibold text-xs leading-tight">
                  {stg.name.split(". ")[1]}
                </div>
                <div className="text-[10px] text-gray-400 mt-1 line-clamp-2 leading-relaxed">
                  {stg.desc}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Real-time SSE Terminal Stream */}
      <div className="rounded-xl glass-panel overflow-hidden border border-white/10">
        {/* Terminal Header Bar */}
        <div className="h-10 bg-black/60 border-b border-white/10 px-4 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-emerald-400" />
            <span className="font-mono text-gray-300 font-semibold">
              SSE Event Stream [/runs/rc_run_01/events]
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
              {events.length} events
            </span>
          </div>

          {/* Filter & Search Controls */}
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="w-3 h-3 absolute left-2 top-2 text-gray-400" />
              <input
                type="text"
                placeholder="Filter logs..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-6 pr-2 py-1 text-[11px] font-mono bg-black/50 border border-white/10 rounded text-gray-200 focus:outline-none focus:border-emerald-500/50 w-32 sm:w-44"
              />
            </div>

            <div className="flex items-center gap-1 bg-black/40 p-0.5 rounded border border-white/10 text-[10px]">
              {["all", "stages", "mutation", "scar"].map((f) => (
                <button
                  key={f}
                  onClick={() => setFilterType(f)}
                  className={`px-2 py-0.5 rounded capitalize ${
                    filterType === f
                      ? "bg-white/15 text-white font-semibold"
                      : "text-gray-400 hover:text-gray-200"
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Terminal Body */}
        <div
          ref={terminalRef}
          className="h-80 overflow-y-auto p-4 bg-[#08090d] font-mono text-xs space-y-1.5 select-text"
        >
          {filteredEvents.map((evt) => (
            <div
              key={evt.seq}
              className="flex items-start gap-2 hover:bg-white/5 py-0.5 px-1 rounded transition-colors"
            >
              <span className="text-gray-600 select-none text-[10px] w-6 shrink-0 text-right">
                {evt.seq}
              </span>
              <span className="text-gray-500 select-none text-[10px] shrink-0">
                [{evt.at}]
              </span>

              <span
                className={`px-1.5 py-0.2 rounded text-[10px] uppercase font-bold shrink-0 ${
                  evt.type.includes("start")
                    ? "bg-blue-500/20 text-blue-400"
                    : evt.type.includes("kill")
                    ? "bg-purple-500/20 text-purple-400"
                    : evt.type.includes("pass")
                    ? "bg-emerald-500/20 text-emerald-400"
                    : evt.type.includes("mint")
                    ? "bg-amber-500/20 text-amber-300 font-bold"
                    : "bg-gray-800 text-gray-300"
                }`}
              >
                {evt.type}
              </span>

              <span className="text-gray-300 text-[11px] break-all">
                {JSON.stringify(evt.payload)}
              </span>
            </div>
          ))}

          {filteredEvents.length === 0 && (
            <div className="text-gray-500 text-center py-12">
              No events match current filter.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
