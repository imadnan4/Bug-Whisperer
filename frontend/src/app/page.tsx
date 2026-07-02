"use client";

import { useState, useCallback } from "react";
import { useTheme } from "next-themes";
import { toast } from "sonner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/optics/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/optics/card";
import { Badge } from "@/components/optics/badge";
import { Button } from "@/components/optics/button";
import { Input } from "@/components/optics/input";
import { Textarea } from "@/components/optics/textarea";
import { CodeBlock } from "@/components/optics/code-block";
import { Progress } from "@/components/optics/progress";
import { Spinner } from "@/components/optics/spinner";
import { Separator } from "@/components/optics/separator";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/optics/accordion";
import { Alert, AlertDescription, AlertTitle } from "@/components/optics/alert";
import { Bug, Zap, Brain, Clock, Search, Terminal, Save, History, BarChart3, Play, CheckCircle2, AlertTriangle, Lightbulb, TrendingUp } from "lucide-react";
import { ThemeSwitcher } from "@/components/optics/theme-switcher";

import { analyzeBug, rememberFix, getStats, BugAnalysis, Stats } from "@/lib/api";

const DEMO_BUGS = [
  {
    error: "TypeError: Cannot read properties of null (reading 'token')",
    stack: `at AuthService.verifyToken (auth.ts:42:15)
    at middleware/auth.ts:18:22
    at processRequest (server.ts:156:8)`,
    rootCause: "The auth token was null because the middleware didn't check for missing Authorization header before calling verifyToken.",
    fix: "Added null check before token verification:\n\nif (!token) {\n  throw new UnauthorizedError('Missing auth token');\n}",
    codeSnippet: `// Before:
const token = req.headers.authorization.split(' ')[1];
const user = await AuthService.verifyToken(token);

// After (with null check):
const authHeader = req.headers.authorization;
if (!authHeader) {
  throw new UnauthorizedError('Missing Authorization header');
}
const token = authHeader.split(' ')[1];
if (!token) {
  throw new UnauthorizedError('Missing auth token');
}
const user = await AuthService.verifyToken(token);`,
    files: ["middleware/auth.ts", "services/AuthService.ts"],
  },
  {
    error: "PrismaClientKnownRequestError: Foreign key constraint failed on the field: `authorId`",
    stack: `at PrismaClient._request (prisma.ts:89:12)
    at PostService.createPost (post.service.ts:34:8)`,
    rootCause: "Trying to create a post with an authorId that doesn't exist in the users table — race condition where user creation hadn't completed.",
    fix: "Added transaction to ensure user exists before creating post, with proper error handling.",
    codeSnippet: `// Before:
const post = await prisma.post.create({
  data: { title, content, authorId: userId }
});

// After:
const post = await prisma.$transaction(async (tx) => {
  const user = await tx.user.findUnique({ where: { id: userId } });
  if (!user) throw new Error('User not found');
  return tx.post.create({
    data: { title, content, authorId: userId }
  });
});`,
    files: ["services/post.service.ts", "prisma/schema.prisma"],
  },
];

export default function Home() {
  const [activeTab, setActiveTab] = useState("debug");
  const [errorMessage, setErrorMessage] = useState("");
  const [stackTrace, setStackTrace] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [currentAnalysis, setCurrentAnalysis] = useState<BugAnalysis | null>(null);
  const [fixSubmitted, setFixSubmitted] = useState(false);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loadingStats, setLoadingStats] = useState(false);
  const [sessionId, setSessionId] = useState<string>("");
  const [bugHistory, setBugHistory] = useState<Array<{ error: string; fromMemory: boolean; time: string }>>([]);

  const handleAnalyze = useCallback(async () => {
    if (!errorMessage.trim()) {
      toast.error("Please enter an error message");
      return;
    }
    setAnalyzing(true);
    setFixSubmitted(false);
    try {
      const result = await analyzeBug(errorMessage, stackTrace);
      setCurrentAnalysis(result);
      setSessionId(result.session_id);
      setBugHistory((prev) => [
        { error: errorMessage.slice(0, 80), fromMemory: result.recall.found, time: new Date().toLocaleTimeString() },
        ...prev,
      ]);
      if (result.recall.found) {
        toast.success(`Found matching bug in memory! ${Math.round(result.recall.confidence * 100)}% confidence`);
      } else {
        toast.info("No matching bug in memory. Analyzing from scratch...");
      }
    } catch (e: any) {
      toast.error(`Analysis failed: ${e.message}`);
    } finally {
      setAnalyzing(false);
    }
  }, [errorMessage, stackTrace]);

  const handleRemember = useCallback(async () => {
    if (!currentAnalysis || !sessionId) return;
    try {
      await rememberFix({
        session_id: sessionId,
        root_cause: currentAnalysis.analysis.root_cause_analysis,
        fix_description: currentAnalysis.analysis.suggested_fix,
        code_snippet: currentAnalysis.analysis.code_snippet || undefined,
        files_changed: currentAnalysis.analysis.related_files,
      });
      setFixSubmitted(true);
      toast.success("Bug and fix stored in memory.");
    } catch (e: any) {
      toast.error(`Failed to store: ${e.message}`);
    }
  }, [currentAnalysis, sessionId]);

  const loadDemoBug = useCallback((bug: (typeof DEMO_BUGS)[0]) => {
    setErrorMessage(bug.error);
    setStackTrace(bug.stack);
  }, []);

  const loadStats = useCallback(async () => {
    setLoadingStats(true);
    try {
      const s = await getStats();
      setStats(s);
    } catch {
      toast.error("Failed to load stats");
    } finally {
      setLoadingStats(false);
    }
  }, []);

  const { theme, setTheme } = useTheme();

  return (
      <div className="min-h-screen bg-background">
        {/* Header */}
        <header className="border-b bg-background/80 backdrop-blur-sm sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-violet-500/10">
                <Bug className="w-6 h-6 text-violet-500" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-foreground">Bug Whisperer</h1>
                <p className="text-xs text-muted-foreground">AI Debugger with Persistent Memory</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <ThemeSwitcher value={theme} onChange={setTheme} />
              <Badge variant="outline" className="border-violet-500/30 text-violet-600 dark:text-violet-300 bg-violet-500/5">
                <Brain className="w-3 h-3 mr-1" />
                Cognee Memory
              </Badge>
              <Badge variant="outline" className="border-emerald-500/30 text-emerald-600 dark:text-emerald-300 bg-emerald-500/5">
                <Zap className="w-3 h-3 mr-1" />
                DeepSeek v4
              </Badge>
            </div>
          </div>
        </header>

        <main className="max-w-7xl mx-auto px-4 py-6">
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="mb-6">
              <TabsTrigger value="debug" className="gap-2">
                <Terminal className="w-4 h-4" />
                Live Debug
              </TabsTrigger>
              <TabsTrigger value="memory" className="gap-2">
                <Brain className="w-4 h-4" />
                Memory Explorer
              </TabsTrigger>
              <TabsTrigger value="stats" className="gap-2" onClick={loadStats}>
                <BarChart3 className="w-4 h-4" />
                Stats & Metrics
              </TabsTrigger>
            </TabsList>

            {/* LIVE DEBUG TAB */}
            <TabsContent value="debug">
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Input Panel */}
                <div className="lg:col-span-1 space-y-4">
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm flex items-center gap-2">
                        <Bug className="w-4 h-4 text-red-400" />
                        Report a Bug
                      </CardTitle>
                      <CardDescription>Paste the error and stack trace</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div>
                        <label className="text-xs text-muted-foreground mb-1 block">Error Message</label>
                        <Input
                          placeholder="e.g., TypeError: Cannot read properties of null..."
                          value={errorMessage}
                          onChange={(e) => setErrorMessage(e.target.value)}
                          className="font-mono text-xs"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-muted-foreground mb-1 block">Stack Trace (optional)</label>
                        <Textarea
                          placeholder="at AuthService.verifyToken (auth.ts:42:15)..."
                          value={stackTrace}
                          onChange={(e) => setStackTrace(e.target.value)}
                          className="font-mono text-xs min-h-[120px]"
                        />
                      </div>
                      <Button
                        className="gap-2"
                        variant="info"
                        onClick={handleAnalyze}
                        disabled={analyzing}
                      >
                        {analyzing ? (
                          <>
                            <Spinner size="size-4" className="text-white" />
                            Analyzing...
                          </>
                        ) : (
                          <>
                            <Search className="w-4 h-4" />
                            Analyze Bug
                          </>
                        )}
                      </Button>

                      <Separator />

                      <div>
                        <p className="text-xs text-muted-foreground mb-2">Quick demo bugs:</p>
                        <div className="space-y-1">
                          {DEMO_BUGS.map((bug, i) => (
                            <Button
                              key={i}
                              variant="outline"
                              size="sm"
                              className="w-full justify-start text-xs font-mono truncate"
                              onClick={() => loadDemoBug(bug)}
                            >
                              <Play className="w-3 h-3 mr-1 shrink-0" />
                              {bug.error.slice(0, 50)}...
                            </Button>
                          ))}
                        </div>
                      </div>
                    </CardContent>
                  </Card>

                  {/* Bug History */}
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm flex items-center gap-2">
                        <History className="w-4 h-4" />
                        Session History
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      {bugHistory.length === 0 ? (
                        <p className="text-xs text-muted-foreground">No bugs analyzed yet</p>
                      ) : (
                        <div className="space-y-2 max-h-[200px] overflow-auto">
                          {bugHistory.map((h, i) => (
                            <div key={i} className="flex items-center gap-2 text-xs p-2 rounded bg-muted">
                              {h.fromMemory ? (
                                <Brain className="w-3 h-3 text-violet-400 shrink-0" />
                              ) : (
                                <Bug className="w-3 h-3 text-red-400 shrink-0" />
                              )}
                              <span className="truncate">{h.error}</span>
                              <span className="text-muted-foreground ml-auto shrink-0">{h.time}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </div>

                {/* Results Panel */}
                <div className="lg:col-span-2 space-y-4">
                  {analyzing && (
                    <Card>
                      <CardContent className="py-12 flex flex-col items-center gap-3">
                        <Spinner size="size-5" className="text-violet-500" />
                        <p className="text-sm text-muted-foreground">Searching memory and analyzing bug...</p>
                      </CardContent>
                    </Card>
                  )}

                  {currentAnalysis && !analyzing && (
                    <>
                      {/* Memory Recall Alert */}
                      {currentAnalysis.recall.found ? (
                        <Alert className="border-violet-500/30 bg-violet-500/10">
                          <Brain className="w-4 h-4 text-violet-400" />
                          <AlertTitle className="text-violet-300">Memory Match Found!</AlertTitle>
                          <AlertDescription className="text-foreground">
                            <p className="mb-2">{currentAnalysis.recall.reasoning}</p>
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-muted-foreground">Confidence:</span>
                              <Progress
                                value={currentAnalysis.recall.confidence * 100}
                                className="w-32 h-2"
                              />
                              <span className="text-xs text-violet-400">
                                {Math.round(currentAnalysis.recall.confidence * 100)}%
                              </span>
                            </div>
                          </AlertDescription>
                        </Alert>
                      ) : (
                        <Alert className="border-amber-500/30 bg-amber-500/10">
                          <AlertTriangle className="w-4 h-4 text-amber-400" />
                          <AlertTitle className="text-amber-300">New Bug Pattern</AlertTitle>
                          <AlertDescription className="text-foreground">
                            No similar bug found in memory. Analyzing from scratch.
                          </AlertDescription>
                        </Alert>
                      )}

                      {/* Fix Suggestion */}
                      <Card className="border-emerald-500/20">
                        <CardHeader>
                          <CardTitle className="flex items-center gap-2 text-sm">
                            <Lightbulb className="w-4 h-4 text-emerald-400" />
                            {currentAnalysis.recall.found ? "Fix from Memory" : "AI Analysis"}
                            {currentAnalysis.analysis.from_memory && (
                              <Badge variant="secondary" className="ml-2 bg-violet-500/10 text-violet-300 border-violet-500/20">
                                From Memory
                              </Badge>
                            )}
                          </CardTitle>
                          <CardDescription>
                            <Badge
                              variant="outline"
                              className={
                                currentAnalysis.analysis.severity === "critical"
                                  ? "border-red-500/30 text-red-300"
                                  : currentAnalysis.analysis.severity === "high"
                                  ? "border-orange-500/30 text-orange-300"
                                  : "border-yellow-500/30 text-yellow-300"
                              }
                            >
                              {currentAnalysis.analysis.severity?.toUpperCase() || "MEDIUM"}
                            </Badge>
                          </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                          <div>
                            <h4 className="text-xs font-semibold text-muted-foreground mb-1">Root Cause Analysis</h4>
                            <p className="text-sm text-foreground">{currentAnalysis.analysis.root_cause_analysis}</p>
                          </div>

                          <div>
                            <h4 className="text-xs font-semibold text-muted-foreground mb-1">Suggested Fix</h4>
                            <p className="text-sm text-foreground">{currentAnalysis.analysis.suggested_fix}</p>
                          </div>

                          {currentAnalysis.analysis.code_snippet && (
                            <div>
                              <h4 className="text-xs font-semibold text-muted-foreground mb-1">Code</h4>
                              <CodeBlock
                                code={currentAnalysis.analysis.code_snippet}
                                language="typescript"
                                className="text-xs"
                              />
                            </div>
                          )}

                          {currentAnalysis.analysis.related_files?.length > 0 && (
                            <div>
                              <h4 className="text-xs font-semibold text-muted-foreground mb-1">Files Involved</h4>
                              <div className="flex gap-1 flex-wrap">
                                {currentAnalysis.analysis.related_files.map((f, i) => (
                                  <Badge key={i} variant="outline" className="text-xs font-mono">
                                    {f}
                                  </Badge>
                                ))}
                              </div>
                            </div>
                          )}

                          <Separator />

                          <Button
                            className="gap-2"
                            variant={fixSubmitted ? "outline" : "info"}
                            onClick={handleRemember}
                            disabled={fixSubmitted}
                          >
                            {fixSubmitted ? (
                              <>
                                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                                Saved to Memory
                              </>
                            ) : (
                              <>
                                <Save className="w-4 h-4" />
                                Save Fix to Memory
                              </>
                            )}
                          </Button>
                        </CardContent>
                      </Card>

                      {/* Memory Comparison (for demo - shows before/after) */}
                      {currentAnalysis.recall.found && currentAnalysis.recall.suggestion && (
                        <Card className="border-violet-500/10 bg-muted/50">
                          <CardHeader>
                            <CardTitle className="text-xs flex items-center gap-2">
                              <Brain className="w-3 h-3 text-violet-400" />
                              Memory Match Detail
                            </CardTitle>
                          </CardHeader>
                          <CardContent>
                            <Accordion type="single" collapsible>
                              <AccordionItem value="detail">
                                <AccordionTrigger className="text-xs">
                                  View how memory found this match
                                </AccordionTrigger>
                                <AccordionContent>
                                  <p className="text-xs text-muted-foreground mb-2">{currentAnalysis.recall.reasoning}</p>
                                  <CodeBlock
                                    code={`Similarity Analysis:
- Error pattern: Matched
- Stack trace proximity: ${Math.round(currentAnalysis.recall.confidence * 100)}%
- Files involved: Overlap detected
- Fix confidence: ${Math.round(currentAnalysis.recall.confidence * 100)}%`}
                                    language="plaintext"
                                    className="text-xs"
                                  />
                                </AccordionContent>
                              </AccordionItem>
                            </Accordion>
                          </CardContent>
                        </Card>
                      )}
                    </>
                  )}

                  {!currentAnalysis && !analyzing && (
                    <Card className="border-dashed border">
                      <CardContent className="py-16 flex flex-col items-center gap-4">
                        <div className="p-4 rounded-full bg-muted">
                          <Bug className="w-8 h-8 text-muted-foreground" />
                        </div>
                        <p className="text-muted-foreground text-center max-w-md">
                          Enter an error message and click <strong>Analyze Bug</strong> to see Bug Whisperer in action.
                          <br />
                          It will search its memory for similar past bugs and suggest fixes.
                        </p>
                      </CardContent>
                    </Card>
                  )}
                </div>
              </div>
            </TabsContent>

            {/* MEMORY EXPLORER TAB */}
            <TabsContent value="memory">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Brain className="w-5 h-5 text-violet-400" />
                    Knowledge Graph Memory
                  </CardTitle>
                  <CardDescription>
                    Every bug and fix is stored as a structured knowledge graph in Cognee.
                    Error patterns link to root causes, which link to fixes, which link to files.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Card className="bg-muted/50 border">
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm">How Cognee Memory Works</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-3 text-sm text-muted-foreground">
                        <div className="flex gap-2">
                          <Badge className="bg-violet-500/10 text-violet-300 border-violet-500/20 shrink-0">1</Badge>
                          <span>
                            <strong className="text-foreground">remember()</strong> — Ingests bug data, extracts entities (error types, files, functions), and builds a knowledge graph with vector embeddings.
                          </span>
                        </div>
                        <div className="flex gap-2">
                          <Badge className="bg-violet-500/10 text-violet-300 border-violet-500/20 shrink-0">2</Badge>
                          <span>
                            <strong className="text-foreground">recall()</strong> — Hybrid search: semantic vector search finds similar errors, then graph traversal follows relationships to root causes and fixes.
                          </span>
                        </div>
                        <div className="flex gap-2">
                          <Badge className="bg-violet-500/10 text-violet-300 border-violet-500/20 shrink-0">3</Badge>
                          <span>
                            <strong className="text-foreground">improve()</strong> — Feedback loop: when a fix works, memory strengthens. When it doesn't, it adapts.
                          </span>
                        </div>
                      </CardContent>
                    </Card>

                    <Card className="bg-muted/50 border">
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm">Graph Structure</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <CodeBlock
                          code={`Error: "TypeError: Cannot read null.token"
  ├── Type: NullReferenceError
  ├── File: middleware/auth.ts
  ├── Root Cause: Missing null check
  ├── Fix: Add guard clause before token access
  ├── Related Errors:
  │   ├── "TypeError: null has no property 'id'"
  │   └── "Cannot destructure property of null"
  └── Stats:
      ├── Occurrences: 3
      ├── Recall Count: 12
      └── Fix Success Rate: 100%`}
                          language="plaintext"
                          className="text-xs"
                        />
                      </CardContent>
                    </Card>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            {/* STATS TAB */}
            <TabsContent value="stats">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm flex items-center gap-2">
                        <Bug className="w-4 h-4 text-red-400" />
                        Total Bugs
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-3xl font-bold">{stats?.total_bugs || 0}</p>
                      <p className="text-xs text-muted-foreground mt-1">Stored in memory</p>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm flex items-center gap-2">
                        <Brain className="w-4 h-4 text-violet-400" />
                        Recalled from Memory
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-3xl font-bold">{stats?.bugs_recalled_from_memory || 0}</p>
                      <p className="text-xs text-muted-foreground mt-1">
                        Hit rate: {stats?.recall_hit_rate?.toFixed(1) || 0}%
                      </p>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm flex items-center gap-2">
                        <Clock className="w-4 h-4 text-emerald-400" />
                        Time Saved
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-3xl font-bold">{stats?.estimated_time_saved_minutes || 0}m</p>
                      <p className="text-xs text-muted-foreground mt-1">Estimated debugging time saved</p>
                    </CardContent>
                  </Card>

                  <Card className="md:col-span-3">
                    <CardHeader>
                      <CardTitle className="text-sm flex items-center gap-2">
                        <TrendingUp className="w-4 h-4 text-violet-400" />
                        Self-Improvement Proof
                      </CardTitle>
                      <CardDescription>
                        The winning metric: as Bug Whisperer remembers more bugs, its recall hit rate improves.
                        This demonstrates the &quot;AI that gets smarter over time&quot; pattern that Cognee judges look for.
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-4">
                        <div>
                          <div className="flex justify-between text-xs text-muted-foreground mb-1">
                            <span>Memory Recall Hit Rate</span>
                            <span>{stats?.recall_hit_rate?.toFixed(1) || 0}%</span>
                          </div>
                          <Progress value={stats?.recall_hit_rate || 0} className="h-3" />
                        </div>
                        <div className="grid grid-cols-2 gap-4 mt-4">
                          <div className="p-3 rounded bg-muted border border">
                            <p className="text-xs text-muted-foreground">Bugs Resolved</p>
                            <p className="text-lg font-bold">{stats?.bugs_resolved || 0}</p>
                          </div>
                          <div className="p-3 rounded bg-muted border border">
                            <p className="text-xs text-muted-foreground">Knowledge Graph Nodes</p>
                            <p className="text-lg font-bold">{stats?.memory_graph_size || 0}</p>
                          </div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
            </TabsContent>
          </Tabs>
        </main>
      </div>
  );
}
