import { useCallback, useEffect, useMemo, useState } from "react";
import {
  createRun,
  createSuite,
  createVersion,
  deleteSuite,
  getRun,
  getRunEvents,
  getRunResult,
  getSuites,
  getTomlSettings,
  listVersions,
  streamRunEvents,
  updateSuite,
  updateTomlSettings,
} from "./api";
import type { PageKey, RunEvent, RunJob, Suite, SuiteVersion, TomlSettings } from "./types";

type RunMode = "real" | "mock";
type TestSelectionMap = Record<string, Set<string>>;
type VersionsMap = Record<string, SuiteVersion[]>;

function testRows(version: SuiteVersion | undefined): Array<{ name: string; paramName: string; valueText: string }> {
  if (!version) return [];
  const tests = version.parsed_json.tests;
  if (!Array.isArray(tests)) return [];

  return tests
    .map((item) => {
      if (typeof item !== "object" || !item) return null;
      const obj = item as Record<string, unknown>;
      const name = typeof obj.name === "string" ? obj.name : "unknown";
      const tp = (obj.test_param ?? {}) as Record<string, unknown>;
      const paramName = typeof tp.name === "string" ? tp.name : "baseline";
      const valueText = tp.value === undefined ? "-" : JSON.stringify(tp.value);
      return { name, paramName, valueText };
    })
    .filter((it): it is { name: string; paramName: string; valueText: string } => Boolean(it));
}

function versionById(versionsBySuite: VersionsMap, suiteId: string, versionId?: string): SuiteVersion | undefined {
  const versions = versionsBySuite[suiteId] ?? [];
  if (versions.length === 0) return undefined;
  if (!versionId) return versions[0];
  return versions.find((v) => v.id === versionId) ?? versions[0];
}

export default function App(): JSX.Element {
  const [page, setPage] = useState<PageKey>("testing");
  const [suites, setSuites] = useState<Suite[]>([]);
  const [versionsBySuite, setVersionsBySuite] = useState<VersionsMap>({});
  const [selectedSuiteId, setSelectedSuiteId] = useState<string | null>(null);

  const [selectedProviders, setSelectedProviders] = useState<Set<string>>(new Set<string>());
  const [selectedSuiteIds, setSelectedSuiteIds] = useState<Set<string>>(new Set<string>());
  const [selectedVersionBySuite, setSelectedVersionBySuite] = useState<Record<string, string>>({});
  const [selectedTestsBySuite, setSelectedTestsBySuite] = useState<TestSelectionMap>({});
  const [expandedProviders, setExpandedProviders] = useState<Set<string>>(new Set<string>());
  const [expandedSuites, setExpandedSuites] = useState<Set<string>>(new Set<string>());
  const [runMode, setRunMode] = useState<RunMode>("real");

  const [runs, setRuns] = useState<RunJob[]>([]);
  const [runEventsById, setRunEventsById] = useState<Record<string, RunEvent[]>>({});
  const [runResultById, setRunResultById] = useState<Record<string, Record<string, unknown>>>({});

  const [toml, setToml] = useState<TomlSettings | null>(null);
  const [notice, setNotice] = useState<string>("");

  const providers = useMemo(() => Array.from(new Set(suites.map((s) => s.provider))).sort(), [suites]);

  const getSuiteById = useCallback((suiteId: string) => suites.find((s) => s.id === suiteId), [suites]);

  const loadSuites = useCallback(async (): Promise<void> => {
    const nextSuites = await getSuites();
    const versionsEntries = await Promise.all(
      nextSuites.map(async (suite) => [suite.id, await listVersions(suite.id)] as const),
    );
    const nextVersionsBySuite = Object.fromEntries(versionsEntries) as VersionsMap;

    setSuites(nextSuites);
    setVersionsBySuite(nextVersionsBySuite);

    setSelectedSuiteId((prev) => {
      if (!nextSuites.length) return null;
      if (prev && nextSuites.some((s) => s.id === prev)) return prev;
      return nextSuites[0].id;
    });

    setSelectedProviders((prev) => {
      if (prev.size > 0) return prev;
      return new Set(nextSuites.map((s) => s.provider));
    });

    setExpandedProviders((prev) => {
      if (prev.size > 0) return prev;
      const first = nextSuites[0]?.provider;
      return first ? new Set([first]) : prev;
    });

    setSelectedVersionBySuite((prev) => {
      const next = { ...prev };
      nextSuites.forEach((suite) => {
        const versions = nextVersionsBySuite[suite.id] ?? [];
        if (!versions.length) return;
        const exists = versions.some((v) => v.id === next[suite.id]);
        if (!exists) next[suite.id] = versions[0].id;
      });
      return next;
    });

    setSelectedSuiteIds((prev) => {
      const valid = new Set(nextSuites.map((s) => s.id));
      return new Set(Array.from(prev).filter((id) => valid.has(id)));
    });

    setSelectedTestsBySuite((prev) => {
      const valid = new Set(nextSuites.map((s) => s.id));
      const next: TestSelectionMap = {};
      Object.entries(prev).forEach(([suiteId, bucket]) => {
        if (valid.has(suiteId)) next[suiteId] = new Set(bucket);
      });
      return next;
    });
  }, []);

  const upsertRun = useCallback((run: RunJob): void => {
    setRuns((prev) => {
      const idx = prev.findIndex((r) => r.id === run.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = run;
        return next;
      }
      return [run, ...prev];
    });
  }, []);

  const pushEvent = useCallback((runId: string, event: RunEvent): void => {
    setRunEventsById((prev) => {
      const history = prev[runId] ?? [];
      return { ...prev, [runId]: [event, ...history].slice(0, 120) };
    });
  }, []);

  const finalizeRun = useCallback(
    async (runId: string, latestSeq: number): Promise<void> => {
      const [job, tailEvents] = await Promise.all([getRun(runId), getRunEvents(runId, latestSeq)]);
      upsertRun(job);
      if (tailEvents.length > 0) {
        setRunEventsById((prev) => {
          const existing = prev[runId] ?? [];
          const appended = [...tailEvents].reverse();
          return { ...prev, [runId]: [...appended, ...existing].slice(0, 120) };
        });
      }

      try {
        const result = await getRunResult(runId);
        setRunResultById((prev) => ({ ...prev, [runId]: result }));
      } catch {
        // Ignore result loading failures for unfinished runs.
      }
    },
    [upsertRun],
  );

  const attachRunStream = useCallback(
    (runId: string): void => {
      let latestSeq = 0;
      const source = streamRunEvents(runId, 0);

      const onDataEvent = async (raw: MessageEvent): Promise<void> => {
        const event = JSON.parse(raw.data) as RunEvent;
        latestSeq = event.seq;
        pushEvent(runId, event);
        if (event.event_type.includes("finished") || event.event_type.includes("started")) {
          const run = await getRun(runId);
          upsertRun(run);
        }
      };

      ["run_started", "test_started", "test_finished", "run_failed", "run_cancelled"].forEach((name) => {
        source.addEventListener(name, (event) => {
          void onDataEvent(event as MessageEvent);
        });
      });

      const finalize = (): void => {
        source.close();
        void finalizeRun(runId, latestSeq);
      };

      source.addEventListener("run_finished", finalize);
      source.addEventListener("done", finalize);
      source.onerror = finalize;
    },
    [finalizeRun, pushEvent, upsertRun],
  );

  const startBatchRun = useCallback(async (): Promise<void> => {
    const suiteIds = Array.from(selectedSuiteIds);
    if (suiteIds.length === 0) {
      setNotice("Pick at least one route to run.");
      return;
    }

    setNotice(`Starting ${suiteIds.length} run(s)...`);

    for (const suiteId of suiteIds) {
      const versionId = selectedVersionBySuite[suiteId];
      if (!versionId) continue;

      const tests = selectedTestsBySuite[suiteId];
      const run = await createRun({
        suite_version_id: versionId,
        mode: runMode,
        selected_tests: tests && tests.size > 0 ? Array.from(tests) : undefined,
      });
      upsertRun(run);
      setRunEventsById((prev) => ({ ...prev, [run.id]: [] }));
      attachRunStream(run.id);
    }

    setNotice("Batch started.");
  }, [attachRunStream, runMode, selectedSuiteIds, selectedTestsBySuite, selectedVersionBySuite, upsertRun]);

  useEffect(() => {
    void loadSuites();
  }, [loadSuites]);

  const selectedTestCount = useMemo(
    () => Object.values(selectedTestsBySuite).reduce((acc, bucket) => acc + bucket.size, 0),
    [selectedTestsBySuite],
  );

  const visibleSuites = useMemo(
    () => suites.filter((suite) => selectedProviders.has(suite.provider)),
    [selectedProviders, suites],
  );

  const visibleSuiteIds = useMemo(() => new Set(visibleSuites.map((s) => s.id)), [visibleSuites]);

  const suiteForCrud = useMemo(() => {
    if (!selectedSuiteId) return null;
    return getSuiteById(selectedSuiteId) ?? null;
  }, [getSuiteById, selectedSuiteId]);

  const versionForCrud = useMemo(() => {
    if (!suiteForCrud) return null;
    return versionById(versionsBySuite, suiteForCrud.id, selectedVersionBySuite[suiteForCrud.id]) ?? null;
  }, [selectedVersionBySuite, suiteForCrud, versionsBySuite]);

  const mergedResults = useMemo(
    () =>
      Object.fromEntries(Object.entries(runResultById).map(([runId, result]) => [runId, result.summary ?? result])),
    [runResultById],
  );

  const onToggleProvider = (provider: string): void => {
    setSelectedProviders((prev) => {
      const next = new Set(prev);
      if (next.has(provider)) next.delete(provider);
      else next.add(provider);
      return next;
    });
    setExpandedProviders((prev) => {
      if (prev.has(provider)) return prev;
      return new Set(prev).add(provider);
    });
  };

  const onProviderSelectAll = (): void => {
    setSelectedProviders(new Set(providers));
    setExpandedProviders(new Set(providers));
  };

  const onProviderClearAll = (): void => {
    setSelectedProviders(new Set());
    setSelectedSuiteIds(new Set());
  };

  const onToggleProviderPanel = (provider: string): void => {
    setExpandedProviders((prev) => {
      const next = new Set(prev);
      if (next.has(provider)) next.delete(provider);
      else next.add(provider);
      return next;
    });
  };

  const onToggleSuite = (suiteId: string): void => {
    setSelectedSuiteIds((prev) => {
      const next = new Set(prev);
      if (next.has(suiteId)) next.delete(suiteId);
      else next.add(suiteId);
      return next;
    });
  };

  const onToggleSuitePanel = (suiteId: string): void => {
    setExpandedSuites((prev) => {
      const next = new Set(prev);
      if (next.has(suiteId)) next.delete(suiteId);
      else next.add(suiteId);
      return next;
    });
  };

  const onToggleTest = (suiteId: string, testName: string, checked: boolean): void => {
    setSelectedTestsBySuite((prev) => {
      const next = { ...prev };
      const bucket = new Set(next[suiteId] ?? []);
      if (checked) bucket.add(testName);
      else bucket.delete(testName);
      next[suiteId] = bucket;
      return next;
    });
  };

  const onCreateSuite = async (): Promise<void> => {
    const provider = window.prompt("Provider", "openai") ?? "openai";
    const endpoint = window.prompt("Endpoint", "/v1/chat/completions") ?? "/v1/chat/completions";
    const name = window.prompt("Suite Name", `${provider} ${endpoint}`) ?? `${provider} ${endpoint}`;
    const raw = `{
  provider: "${provider}",
  endpoint: "${endpoint}",
  schemas: {},
  base_params: {},
  tests: [{ name: "test_baseline", is_baseline: true }]
}`;

    await createSuite({ provider, endpoint, name, raw_json5: raw, created_by: "web-ui" });
    await loadSuites();
    setNotice("Suite created.");
  };

  const onPickCrudSuite = async (suiteId: string): Promise<void> => {
    setSelectedSuiteId(suiteId);
    const versions = await listVersions(suiteId);
    setVersionsBySuite((prev) => ({ ...prev, [suiteId]: versions }));
    if (versions[0]) {
      setSelectedVersionBySuite((prev) => ({ ...prev, [suiteId]: versions[0].id }));
    }
  };

  const onUpdateMeta = async (): Promise<void> => {
    if (!suiteForCrud) return;
    const nameInput = document.getElementById("suite-name") as HTMLInputElement | null;
    const statusInput = document.getElementById("suite-status") as HTMLSelectElement | null;
    const name = (nameInput?.value ?? "").trim();
    const status = (statusInput?.value ?? "active") as "active" | "archived";

    await updateSuite(suiteForCrud.id, { name, status });
    await loadSuites();
    setNotice("Suite metadata updated.");
  };

  const onDeleteSuite = async (): Promise<void> => {
    if (!suiteForCrud) return;
    if (!window.confirm(`Delete suite ${suiteForCrud.name}?`)) return;

    await deleteSuite(suiteForCrud.id);
    await loadSuites();
    setSelectedSuiteIds((prev) => {
      const next = new Set(prev);
      next.delete(suiteForCrud.id);
      return next;
    });
    setSelectedTestsBySuite((prev) => {
      const next = { ...prev };
      delete next[suiteForCrud.id];
      return next;
    });
    setSelectedVersionBySuite((prev) => {
      const next = { ...prev };
      delete next[suiteForCrud.id];
      return next;
    });
    setNotice("Suite deleted.");
  };

  const onSaveNewVersion = async (): Promise<void> => {
    if (!suiteForCrud) return;
    const editor = document.getElementById("suite-json5") as HTMLTextAreaElement | null;
    const raw = editor?.value ?? "";

    await createVersion(suiteForCrud.id, { raw_json5: raw, created_by: "web-ui" });
    const versions = await listVersions(suiteForCrud.id);
    setVersionsBySuite((prev) => ({ ...prev, [suiteForCrud.id]: versions }));
    setSelectedVersionBySuite((prev) => ({ ...prev, [suiteForCrud.id]: versions[0]?.id ?? "" }));
    await loadSuites();
    setNotice("New version saved.");
  };

  const onGotoPage = async (target: PageKey): Promise<void> => {
    setPage(target);
    if (target === "settings" && !toml) {
      const content = await getTomlSettings();
      setToml(content);
    }
  };

  const onLoadToml = async (): Promise<void> => {
    const config = await getTomlSettings();
    setToml(config);
    setNotice("TOML loaded.");
  };

  const onSaveToml = async (): Promise<void> => {
    const editor = document.getElementById("toml-editor") as HTMLTextAreaElement | null;
    const content = editor?.value ?? "";
    const saved = await updateTomlSettings(content);
    setToml(saved);
    setNotice("TOML saved.");
  };

  const renderTestingPage = (): JSX.Element => (
    <>
      <section className="rounded-2xl bg-white p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="text-lg font-bold">Providers Route</div>

          <div className="flex flex-col items-end gap-2" style={{ fontFamily: "var(--font-sans)" }}>
            <div className="flex items-end gap-5 text-slate-700">
              <div className="flex flex-col items-center leading-tight">
                <span className="text-2xl font-semibold">{selectedProviders.size}</span>
                <span className="text-xs font-semibold">providers</span>
              </div>
              <div className="flex flex-col items-center leading-tight">
                <span className="text-2xl font-semibold">{selectedSuiteIds.size}</span>
                <span className="text-xs font-semibold">routes</span>
              </div>
              <div className="flex flex-col items-center leading-tight">
                <span className="text-2xl font-semibold">{selectedTestCount}</span>
                <span className="text-xs font-semibold">tests</span>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          {providers.map((provider) => {
            const total = suites.filter((s) => s.provider === provider).length;
            const active = selectedProviders.has(provider);
            return (
              <button
                key={provider}
                className={`inline-flex items-center gap-1.5 rounded-md border px-3 py-1 text-xs font-semibold ${
                  active ? "border-violet-300 bg-violet-100 text-violet-900" : "border-slate-300 bg-white text-slate-700"
                }`}
                onClick={() => onToggleProvider(provider)}
              >
                {provider}
                <span className="rounded-md border border-violet-200 bg-violet-50 px-1.5 text-[11px] text-violet-700">{total}</span>
              </button>
            );
          })}
          <button
            className="inline-flex items-center rounded-md border border-slate-300 bg-white px-3 py-1 text-xs font-semibold text-slate-700"
            onClick={onProviderSelectAll}
          >
            All
          </button>
          <button
            className="inline-flex items-center rounded-md border border-slate-300 bg-white px-3 py-1 text-xs font-semibold text-slate-700"
            onClick={onProviderClearAll}
          >
            None
          </button>
          <button
            className={`inline-flex items-center rounded-md border px-3 py-1 text-xs font-semibold ${
              runMode === "real" ? "border-violet-300 bg-violet-100 text-violet-900" : "border-slate-300 bg-white text-slate-700"
            }`}
            onClick={() => setRunMode("real")}
          >
            Real
          </button>
          <button
            className={`inline-flex items-center rounded-md border px-3 py-1 text-xs font-semibold ${
              runMode === "mock" ? "border-violet-300 bg-violet-100 text-violet-900" : "border-slate-300 bg-white text-slate-700"
            }`}
            onClick={() => setRunMode("mock")}
          >
            Mock
          </button>
          <button className="inline-flex items-center rounded-md bg-violet-600 px-3 py-1 text-xs font-semibold text-white" onClick={() => void startBatchRun()}>
            Run {selectedSuiteIds.size}
          </button>
        </div>

        <div className="my-4 border-t border-slate-200" />

        <div className="flex flex-col gap-3">
          {providers
            .filter((provider) => selectedProviders.has(provider))
            .map((provider) => {
              const groupSuites = visibleSuites
                .filter((suite) => suite.provider === provider)
                .sort((a, b) => a.endpoint.localeCompare(b.endpoint));
              if (!groupSuites.length) return null;

              const expanded = expandedProviders.has(provider);
              const selectedRouteCount = groupSuites.filter((s) => selectedSuiteIds.has(s.id)).length;

              return (
                <div key={provider} className="rounded-xl border border-slate-300 bg-white p-3">
                  <div className="flex items-center justify-between gap-2">
                    <strong className="text-2xl font-semibold leading-none text-slate-900">{provider}</strong>
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                      <span>
                        {selectedRouteCount}/{groupSuites.length} routes
                      </span>
                      <button
                        className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-slate-200 bg-white text-xs"
                        onClick={() => onToggleProviderPanel(provider)}
                      >
                        {expanded ? "▾" : "▸"}
                      </button>
                    </div>
                  </div>

                  {expanded && (
                    <div className="mt-2 flex flex-col">
                      {groupSuites.map((suite) => {
                        const versions = versionsBySuite[suite.id] ?? [];
                        const selectedVersionId = selectedVersionBySuite[suite.id] ?? versions[0]?.id;
                        const version = versionById(versionsBySuite, suite.id, selectedVersionId);
                        const tests = testRows(version);
                        const selectedTests = selectedTestsBySuite[suite.id] ?? new Set<string>();
                        const testsExpanded = expandedSuites.has(suite.id);
                        const normalizedName = suite.name.trim().toLowerCase();
                        const duplicateName =
                          normalizedName === `${suite.provider} ${suite.endpoint}`.toLowerCase() ||
                          normalizedName === suite.endpoint.toLowerCase();

                        return (
                          <div key={suite.id} className="mt-2 rounded-xl border border-slate-200 bg-slate-50/40 p-2.5">
                            <div className="flex items-center justify-between gap-2">
                              <label className="inline-flex min-w-0 flex-1 items-center gap-2 text-sm font-semibold leading-5 text-slate-900">
                                <input
                                  type="checkbox"
                                  className="h-3.5 w-3.5 accent-violet-600"
                                  checked={selectedSuiteIds.has(suite.id)}
                                  onChange={() => onToggleSuite(suite.id)}
                                />
                                <strong className="truncate">{suite.endpoint}</strong>
                              </label>

                              <div className="flex items-center gap-2">
                                <span className="text-xs text-slate-500">
                                  {selectedTests.size}/{tests.length} selected
                                </span>
                                <select
                                  className="h-8 w-24 rounded-lg border border-slate-300 bg-white px-2 text-xs font-medium text-slate-700"
                                  value={selectedVersionId ?? ""}
                                  onChange={(e) =>
                                    setSelectedVersionBySuite((prev) => ({ ...prev, [suite.id]: e.target.value }))
                                  }
                                >
                                  {versions.map((v) => (
                                    <option key={v.id} value={v.id}>
                                      v{v.version}
                                    </option>
                                  ))}
                                </select>
                                <button
                                  className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-slate-200 bg-white text-xs"
                                  onClick={() => onToggleSuitePanel(suite.id)}
                                >
                                  {testsExpanded ? "▾" : "▸"}
                                </button>
                              </div>
                            </div>

                            {!duplicateName && <div className="my-1 text-xs font-medium text-slate-500">{suite.name}</div>}

                            {testsExpanded ? (
                              <>
                                <div className="flex flex-wrap gap-2">
                                  {tests.length ? (
                                    tests.map((test) => (
                                      <label
                                        key={`${suite.id}:${test.name}`}
                                        title={test.valueText}
                                        className="inline-flex items-center gap-1.5 rounded-full border border-slate-300 bg-white px-3 py-1 text-xs font-semibold text-slate-900"
                                      >
                                        <input
                                          type="checkbox"
                                          className="h-3.5 w-3.5 accent-violet-600"
                                          checked={selectedTests.has(test.name)}
                                          onChange={(e) => onToggleTest(suite.id, test.name, e.target.checked)}
                                        />
                                        {test.paramName}
                                      </label>
                                    ))
                                  ) : (
                                    <span className="text-xs text-slate-500">No test cases.</span>
                                  )}
                                </div>
                              </>
                            ) : null}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}

          {visibleSuites.length === 0 && <p className="m-0 text-sm text-slate-500">No routes for current filters.</p>}
        </div>

        <div className="mt-2 text-xs text-slate-500">Visible routes: {visibleSuiteIds.size}</div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-[inset_0_0_0_1px_#eef1f7]">
        <div className="text-lg font-bold">Runs</div>
        <div className="mt-2 grid grid-cols-1 gap-2 xl:grid-cols-2">
          {runs.length === 0 && <p className="m-0 text-sm text-slate-500">No runs yet.</p>}

          {runs.map((run) => {
            const events = runEventsById[run.id] ?? [];
            const summary = runResultById[run.id]?.summary as Record<string, unknown> | undefined;
            return (
              <div key={run.id} className="rounded-xl bg-slate-50 p-3">
                <div className="text-sm font-bold">
                  <strong>{run.provider}</strong> {run.endpoint}
                </div>
                <div className="mt-1 font-mono text-[11px] text-slate-500">{run.id}</div>

                <div className="mt-2 grid grid-cols-3 gap-1.5 text-xs">
                  <span className="rounded-lg border border-slate-200 p-1.5 text-slate-500">
                    Status <b className="ml-1 text-slate-900">{run.status}</b>
                  </span>
                  <span className="rounded-lg border border-slate-200 p-1.5 text-slate-500">
                    Progress <b className="ml-1 text-slate-900">{run.progress_done}/{run.progress_total}</b>
                  </span>
                  <span className="rounded-lg border border-slate-200 p-1.5 text-slate-500">
                    Pass/Fail <b className="ml-1 text-slate-900">{run.progress_passed}/{run.progress_failed}</b>
                  </span>
                </div>

                {summary && (
                  <div className="mt-1.5 grid grid-cols-3 gap-1.5 text-xs">
                    <span className="rounded-lg border border-slate-200 p-1.5 text-slate-500">
                      Total <b className="ml-1 text-slate-900">{String(summary.total ?? "-")}</b>
                    </span>
                    <span className="rounded-lg border border-slate-200 p-1.5 text-slate-500">
                      Passed <b className="ml-1 text-slate-900">{String(summary.passed ?? "-")}</b>
                    </span>
                    <span className="rounded-lg border border-slate-200 p-1.5 text-slate-500">
                      Failed <b className="ml-1 text-slate-900">{String(summary.failed ?? "-")}</b>
                    </span>
                  </div>
                )}

                <div className="mt-2 max-h-28 overflow-auto rounded-lg border border-slate-200 bg-white">
                  {events.slice(0, 8).map((event) => (
                    <div
                      key={event.id}
                      className="flex items-center justify-between border-b border-slate-100 px-2 py-1.5 text-xs last:border-b-0"
                    >
                      <span>{event.event_type}</span>
                      <small className="text-slate-500">#{event.seq}</small>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-[inset_0_0_0_1px_#eef1f7]">
        <div className="text-lg font-bold">Result Snapshot</div>
        <pre className="mt-2 max-h-80 overflow-auto rounded-xl bg-slate-950 p-3 font-mono text-xs text-slate-100">
          {JSON.stringify(mergedResults, null, 2)}
        </pre>
      </section>
    </>
  );

  const renderSuitesPage = (): JSX.Element => {
    const versions = suiteForCrud ? versionsBySuite[suiteForCrud.id] ?? [] : [];

    return (
      <>
        <section>
          <h1 className="m-0 text-4xl font-black tracking-tight">Suites</h1>
          <p className="mt-2 text-sm font-medium text-slate-500">Create, update, delete suites and manage JSON5 versions.</p>
        </section>

        <section className="flex flex-wrap gap-2 rounded-2xl border border-slate-200 bg-white p-4">
          <button className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-bold" onClick={() => void onCreateSuite()}>
            Create Suite
          </button>
          <button
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-bold disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!suiteForCrud}
            onClick={() => void onDeleteSuite()}
          >
            Delete Suite
          </button>
          <button
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-bold disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!suiteForCrud}
            onClick={() => void onUpdateMeta()}
          >
            Update Meta
          </button>
          <button
            className="rounded-lg bg-violet-600 px-3 py-2 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!suiteForCrud}
            onClick={() => void onSaveNewVersion()}
          >
            Save New Version
          </button>
        </section>

        <section className="grid grid-cols-1 gap-3 xl:grid-cols-[1fr_1.2fr]">
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="text-lg font-bold">Suite List</div>
            <div className="mt-2 flex max-h-[520px] flex-col gap-2 overflow-auto">
              {suites.length === 0 && <p className="m-0 text-sm text-slate-500">No suites</p>}
              {suites.map((suite) => (
                <button
                  key={suite.id}
                  className={`rounded-xl border px-3 py-2 text-left ${
                    suite.id === suiteForCrud?.id ? "border-violet-300 bg-violet-100" : "border-slate-200 bg-white"
                  }`}
                  onClick={() => void onPickCrudSuite(suite.id)}
                >
                  <strong className="block text-sm font-bold">{suite.name}</strong>
                  <span className="text-xs text-slate-500">
                    {suite.provider} {suite.endpoint} · v{suite.latest_version}
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="mb-2 grid grid-cols-[90px_1fr] items-center gap-2">
              <label className="text-sm font-semibold text-slate-500">Name</label>
              <input
                id="suite-name"
                key={`suite-name-${suiteForCrud?.id ?? "none"}`}
                defaultValue={suiteForCrud?.name ?? ""}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
            </div>

            <div className="mb-2 grid grid-cols-[90px_1fr] items-center gap-2">
              <label className="text-sm font-semibold text-slate-500">Status</label>
              <select
                id="suite-status"
                key={`suite-status-${suiteForCrud?.id ?? "none"}`}
                defaultValue={suiteForCrud?.status ?? "active"}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              >
                <option value="active">active</option>
                <option value="archived">archived</option>
              </select>
            </div>

            <div className="mb-2 flex flex-wrap gap-1.5">
              {versions.map((version) => (
                <button
                  key={version.id}
                  className={`rounded-full border px-2.5 py-1 text-xs font-bold ${
                    version.id === versionForCrud?.id
                      ? "border-violet-600 text-violet-700"
                      : "border-slate-200 text-slate-700"
                  }`}
                  onClick={() =>
                    setSelectedVersionBySuite((prev) => ({
                      ...prev,
                      [version.suite_id]: version.id,
                    }))
                  }
                >
                  v{version.version}
                </button>
              ))}
            </div>

            <textarea
              id="suite-json5"
              key={versionForCrud?.id ?? "empty"}
              defaultValue={versionForCrud?.raw_json5 ?? ""}
              className="min-h-[310px] w-full resize-y rounded-lg border border-slate-200 px-3 py-2 font-mono text-sm"
            />
          </div>
        </section>
      </>
    );
  };

  const renderSettingsPage = (): JSX.Element => (
    <>
      <section>
        <h1 className="m-0 text-4xl font-black tracking-tight">Settings</h1>
        <p className="mt-2 text-sm font-medium text-slate-500">Edit runtime TOML config for providers and report behavior.</p>
      </section>

      <section className="flex flex-wrap gap-2 rounded-2xl border border-slate-200 bg-white p-4">
        <button className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-bold" onClick={() => void onLoadToml()}>
          Load TOML
        </button>
        <button className="rounded-lg bg-violet-600 px-3 py-2 text-sm font-bold text-white" onClick={() => void onSaveToml()}>
          Save TOML
        </button>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="mb-2 text-lg font-bold">{toml?.path ?? "llm-spec.toml"}</div>
        <textarea
          id="toml-editor"
          key={toml?.path ?? "toml"}
          defaultValue={toml?.content ?? ""}
          className="min-h-[320px] w-full resize-y rounded-lg border border-slate-200 px-3 py-2 font-mono text-sm"
        />
      </section>
    </>
  );

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex w-full max-w-[1600px] items-center justify-between px-4 py-3 xl:px-7">
          <div className="flex items-center gap-8">
            <div className="flex items-center gap-2.5">
              <img src="/logo.jpg" alt="logo" className="h-10 w-10 rounded-lg object-cover" />
              <div className="text-[22px] font-black leading-tight">LLM Spec</div>
            </div>

            <nav className="flex items-center gap-1" style={{ fontFamily: "var(--font-sans)" }}>
              {(["testing", "suites", "settings"] as PageKey[]).map((item) => (
                <button
                  key={item}
                  className={`rounded-lg px-3 py-2 text-sm font-medium ${
                    page === item ? "bg-violet-50 text-violet-600" : "text-slate-600 hover:text-slate-900"
                  }`}
                  onClick={() => void onGotoPage(item)}
                >
                  {item[0].toUpperCase() + item.slice(1)}
                </button>
              ))}
            </nav>
          </div>

          <div className="min-h-5 text-right text-xs text-slate-500">{notice}</div>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-[1600px] flex-col gap-3 px-4 py-4 xl:px-7">
        {page === "testing" && renderTestingPage()}
        {page === "suites" && renderSuitesPage()}
        {page === "settings" && renderSettingsPage()}
      </main>
    </div>
  );
}
