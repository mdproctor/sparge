# When the Machine Codes: Against the Python Default in LLM-First Development

**Part 1 of 5 — When the Machine Codes series**  
**Status:** Draft complete. Not yet published.

*This article is published in two parts. Part 1 makes the case; Part 2 delivers the practice. Both are written to be readable by non-technical audiences. Sections that go into implementation detail are marked* [Technical detail] — *the argument holds without them.*

---

When the Sparge blog migration tool was first built, the choice of Python as its server language was never formally made. It simply happened. The system that wrote most of the code — a large language model working from design specifications provided by the human architect — reached for Python by default. No one questioned this. The system ran. It processed HTML, converted posts, managed state. Python was fine.

Then, for reasons unrelated to Python's merits — specifically, the need to bundle the server into an Electron desktop application without shipping a 150-megabyte Python runtime alongside it — a decision was made to port the server component to Java and the Quarkus framework. The port required bridging two languages during the transition, proceeded through six distinct phases, and when complete, something unexpected emerged from the retrospective: the original Python choice could not be defended on any ground specific to this project. Every argument that had implicitly justified it — faster prototyping, lighter syntax, easier iteration — turned out to describe advantages for human developers. The machine that had done the implementation had different properties, and no one had accounted for that.

This article examines what those properties are, why they change the calculus of framework selection, and what the implications are for organisations whose software development increasingly involves large language models as primary implementers rather than as assistants to human coders. The argument is not that Python is a poor language. It is that the assumptions underlying its selection as a default deserve more scrutiny than they typically receive — and that scrutiny changes the answer for a specific and growing class of development context.

A framing note before proceeding: the argument in this series is not specifically about Java. The primary claim — that static typing is better suited than dynamic typing for LLM-first development — applies to any statically typed language. TypeScript, Go, Kotlin, C#, and Rust all share the advantages over Python described in Parts 1 and 2. Java is then argued as the best choice *among* statically typed options for enterprise backend development — on grounds examined empirically in Part 2, where a comparison across six languages is presented. Readers with a preference for another statically typed language will find most of the argument applies to their chosen language.

Part 1 examines the sources of the Python default, the anthropocentric assumptions embedded in conventional prototyping arguments, where Python's advantages remain real, and what an honest decision framework looks like. Part 2 makes the positive case for static typing across four distinct dimensions — then compares six statically typed languages empirically to ground the Java recommendation. Part 3 documents the Sparge migration as a worked example.

---

## 1. How Python Became the Default

Python's dominance in software development did not arise from a collective decision that it was the best general-purpose language. It arose from a sequence of domain-specific victories that accumulated into an assumption of universal applicability.

The first and most significant was data science. When the scientific computing community began migrating from MATLAB and R in the early 2010s, Python — already established as a clean scripting language — absorbed that migration almost entirely. NumPy, SciPy, Pandas, and eventually TensorFlow and PyTorch were written for or in Python. The data science community is large, produces enormous volumes of written material, and that material became training data. By the time large language models were trained on the corpus of public code, Python was not merely common — it was overwhelmingly dominant in precisely the domains most represented in that corpus.

The consequence is measurable. A 2025 study examining eight leading language models — including GPT-4o, Claude, Llama, and DeepSeek — found that LLMs use Python for 90 to 97 percent of all benchmark problems, and that base models achieve their highest pass rates in Python, outperforming Java by 11.3 percentage points. The paper's conclusion is careful: this reflects training data distribution, not evidence that Python produces superior results. The models are not choosing Python because it is better. They are choosing it because it is familiar in the way that a language absorbed through billions of examples becomes familiar — not through reasoning, but through pattern. *(See Appendix 5 for a domain-specific correction to this statistic.)*

This matters because when an LLM recommends Python for a new project, that recommendation is not the output of an analysis weighing Python's properties against the project's requirements. It is the output of a strong prior, shaped by what the model has seen most. The recommendation sounds like a considered judgment. It has the form of a considered judgment. It is not one.

Human developers are not immune to the same dynamic. Python's reputation for being "easy to prototype in" circulates as received wisdom, and received wisdom is rarely examined until it fails. The difference is that human developers can be asked to justify their choices against specific constraints and will often surface the real reasons — team familiarity, existing infrastructure, library requirements. An LLM asked to justify its Python recommendation will produce a fluent justification. That justification will contain the anthropocentric assumptions examined in the next section, presented as though they were properties of the language rather than properties of human cognition. The persuasiveness of the output and the validity of the reasoning are independent variables.

---

## 2. The Anthropocentric Assumption

When developers say that Python is faster to prototype in, they are describing a real phenomenon. But the explanation for it reveals a constraint that does not apply to large language models.

Prototyping speed in Python has three sources. The first is syntactic lightness: less boilerplate, fewer type declarations, no compile step. A function that takes five lines in Python may take fifteen in Java. The second is the REPL — the read-evaluate-print loop that lets a developer run a single expression, inspect the result, and iterate without a build cycle. The third is familiarity: a developer who has written Python for years carries a mental library of patterns, idioms, and library calls that they can produce quickly and accurately.

None of these advantages transfer to a large language model in the way they transfer between human developers.

Syntactic length is not friction for a system that generates text. When an LLM writes a Java record with five fields, package declaration, and imports, or a Python dataclass with the same five fields, the generation process differs only in the number of tokens produced. There is no cognitive load. There is no fatigue. The additional characters in the Java version are not experienced as effort — they are output, and output is what LLMs do. This is not an approximation: it is structurally true of how these systems work.

The REPL advantage does not apply at all. LLMs do not iterate through a read-evaluate-print loop. They generate a complete response. The compile-test-fix cycle is a property of the workflow around the LLM, not a constraint on the LLM itself — and in practice, a Java compilation error caught before runtime eliminates an iteration cycle that a Python runtime error would require.

Familiarity, in the human sense, does not apply either. An LLM does not know Java less well than Python because it has spent less time with it. It knows both through exposure to billions of lines of code from both languages. What does differ is the *distribution* of that exposure — and this is where the real explanation lies. As the study cited in Section 1 found, LLMs use Python for 90 to 97 percent of benchmark problems not because Python produces better results but because Python appears more frequently in training data. The model is not making a reasoned choice. It is following a strong prior.

This distinction matters because the justification offered for the Python default — when it is offered at all — typically borrows from the human prototyping-speed argument. The model recommends Python, and if asked why, it will produce a fluent account citing syntax, iteration speed, and ecosystem. That account is not wrong in the sense of being factually false. It is wrong in the sense of being inapplicable: it describes advantages that belong to human developers and attributes them to the language, without examining whether the human doing the prototyping is, in this case, a machine.

There is a word for reasoning that assumes human properties without examining whether they transfer: anthropocentric. Framework selection for LLM-first development has been anthropocentric in this specific and largely unexamined way.

**The token cost corrective.** One further point inverts the verbosity argument entirely. Research on LLM debugging behaviour — specifically the Debugging Decay Index — shows that models lose 60 to 80 percent of their debugging effectiveness within two to three iterations. Each additional cycle of generate-fail-diagnose-regenerate is not merely more tokens: it is tokens spent on progressively degraded reasoning. A separate body of research finds that 94 percent of LLM-generated compilation errors are type-related. In a dynamically typed language, those errors surface at runtime. In a statically typed language, they surface at compile time — before execution, with precise location information, in a form that the LLM can act on immediately. The direction of this argument is sound: compile-time errors are caught earlier, with less degradation, and at lower total cost than runtime errors caught after full debug cycles. The precise magnitude — how many cycles are saved per implementation unit, and what the net token differential is — is a structural inference. No controlled study yet measures this directly. The verbosity is in the output. The savings are in the cycles. The size of those savings awaits measurement.

**The static analysis advantage.** A third distinction compounds the previous two, and it operates across the entire LLM involvement with a codebase — not only at generation time. When an LLM performs a static read-through of Java code, the type system provides structural information that is compiler-verified. `List<MdIssue>` declares precisely what the list contains. `replay(String md, List<RefinementRule> rules)` is an enforced contract, not a convention. If the code compiled, entire classes of error can be ruled out before the first line of logic is read. The LLM's review findings can be stated with corresponding confidence.

In Python, a static read-through is partially inferential. The LLM must reason about what type a variable holds — from naming conventions, from usage context, from type hints if they exist and are accurate, from docstrings that may be stale. A dictionary carrying keys `check`, `level`, and `detail` offers no structural guarantee that those keys are always present, always of the declared types, or that the same dictionary shape does not appear elsewhere with different content. The review proceeds, but under uncertainty that the type system in Java eliminates by construction.

Python's type system in 2025 is stronger than this characterisation in isolation suggests. Pydantic v2 provides runtime type enforcement — not merely hints — and is the foundation of FastAPI, the dominant modern Python web framework. pyright in strict mode provides compile-equivalent checking. A well-engineered modern Python codebase using these tools is substantially more legible to a cold-reading LLM than untyped Python. The honest comparison is disciplined Python against disciplined Java. That comparison still favours Java — structural enforcement happens at compile time in Java, before execution, whereas Pydantic enforces at runtime data boundaries; and type annotations remain opt-in rather than enforced by construction — but the gap is more precise than a general dismissal of Python typing. Part 2 examines this comparison in full.

The implication extends beyond code review. Every point at which an LLM reasons about a codebase — assessing the impact of a change, locating a bug, evaluating a refactoring — benefits from lower uncertainty about what the code is doing. Static typing does not make LLMs infallible reviewers. It removes a systematic source of ambiguity that dynamic typing leaves open. In a development model where the LLM is the primary implementer and the human is the architect and reviewer, that reduction in ambiguity accumulates across every interaction with the code.

---

## 3. Design Spec-Led Development

The argument in Sections 1 and 2 rests on a specific premise: that the entity doing the implementation is a large language model, not a human. This is not yet the universal condition of software development, but it is a direction of travel — and for the purposes of this article, it describes a development model that is already in practical use.

The model operates as follows. The human architect authors a design specification: a precise description of what is to be built, how components interact, what the data contracts are, and what the acceptance criteria look like. The LLM implements against that specification — writing the code, the tests, and the documentation. The human reviews the output, identifies gaps between the implementation and the specification, and iterates. The cycle is specification, implementation, review — not the traditional pair programming model of human writes, human reviews, human merges.

This is not the same as asking an LLM to write some code and accepting whatever emerges. The specification is the load-bearing element. A precise specification produces a precise implementation; an underspecified one produces something that may work but cannot be verified to be correct without running it. The discipline of writing the specification before the implementation forces clarity about what is actually required — a discipline that has value independent of who or what does the implementation.

In this model, the human's language preference carries less weight than it does in traditional development, but it does not disappear. The human still reviews the implementation — and readability matters for review. When an LLM produces confused or misaligned output, the human may need to intervene directly or write a small code fragment to demonstrate the intended pattern or approach. These are real interactions with the code. What changes is not whether the human touches the code, but how much of the total implementation passes through their hands, and therefore how much influence their personal typing ergonomics should exert on the framework decision. The question of whether Java or Python is more comfortable to type remains a legitimate input — but in a model where the LLM authors the bulk of the implementation, it is no longer the dominant one. Other criteria, examined in Section 4, carry more weight.

What does arise is a different set of requirements. The framework must produce output that the LLM can implement reliably, review accurately, and reason about when it needs to explain or extend the system. It must support the static analysis that makes review meaningful. It must integrate cleanly into a deployment context without friction that was not present in the specification. And it must produce systems that can be maintained and extended in future sessions by an LLM that has no memory of the previous one, working only from the code and whatever specification documents remain.

This last point is underappreciated. A human developer carries context between sessions in their memory. An LLM does not. Every session begins with a cold read of the codebase. The quality of that cold read — how accurately the LLM can reconstruct the system's intent and current state from the code alone — determines how effectively the next session can proceed. A statically typed codebase with explicit data contracts, well-named records, and compiler-enforced interfaces is substantially more legible in a cold read than a dynamically typed one where structure must be inferred from usage. The type system, in this sense, is not only a quality mechanism. It is a continuity mechanism — the means by which context persists across the session boundary that LLMs cannot bridge themselves.

*The Sparge system was built in this model. The companion study in Part 5 examines the same model applied in parallel across a suite of integrated systems. Together they constitute the empirical basis for the claims in this article; that basis is introduced here and developed in full there.*

---

## 4. The Case for Java and Quarkus in LLM-First Development

The preceding sections have argued against Python on grounds that the standard justifications for it do not transfer to LLM-first development. This section makes the positive case: the specific properties of Java and Quarkus that make them well-suited to this development model, on grounds that are real rather than inherited.

**Type system as specification enforcement.** In the design spec-led model, the specification describes what is to be built. The type system, once the implementation exists, verifies that what was built conforms to the structural contracts the specification implied. A record defined as `RefinementRule(String check, int fenceIndex, String fingerprint, String contentSample, Map<String, String> fix)` is not merely a data structure — it is a machine-readable encoding of a design decision. It cannot be partially populated, cannot be passed where a different type is expected, and cannot be silently misread. When the LLM generates code that uses this record incorrectly, the compiler says so immediately and precisely. When a future session reads this code cold, it knows without ambiguity what the contract is. *(See also Appendices 1, 3, and 4.)*

In the Sparge project, Java's compiler caught three substantive errors during implementation that would have been silent in Python: an incorrect argument order in a constructor call, a multi-fence aggregation that produced one result where N were required, and a dead parameter that the function signature declared but the implementation never used. None of these produced runtime errors in the test cases written at the time. All would have surfaced later, in contexts harder to diagnose.

**Quarkus-specific properties.** Quarkus is not incidental to this argument. Its design choices compound the advantages of Java's type system in ways relevant to LLM-first development. JAX-RS annotations make REST endpoint declarations explicit and structural — the LLM generating a new endpoint follows a pattern that is both machine-verifiable and immediately legible in review. CDI dependency injection is declared rather than implicit. Records and sealed types make data contracts self-documenting. The LLM does not need to infer what a component does from its behaviour; it can read what the component declares itself to be.

Quarkus's fast startup — demonstrated at under one second in the Sparge deployment — makes it viable for desktop embedding in a way that traditional application servers are not. The uber-jar packaging model produces a single deployable artifact of approximately 19 megabytes, compared to the 150 megabytes required to bundle a Python runtime into the same Electron application. These are not language advantages in the abstract; they are concrete properties that determined the outcome of a real deployment decision. *(See Appendix 2 for the concurrency model advantage.)*

**At scale: parallel development and integration coherence.** The advantages described above compound when development is not a single project but a suite of related systems developing concurrently. When multiple systems share integration contracts — REST APIs, event schemas, shared data types — the static type system makes those contracts explicit and machine-verifiable from each system's side independently. An LLM working on System B can inspect System A's declared types and verify its side of the integration without running both systems together. A change to System A's API surface is visible immediately as a compilation failure in System B, not as a runtime failure discovered during integration testing.

In a dynamically typed system at the same scale, each integration point is a convention — documented somewhere, maintained by discipline, invisible to the compiler. As the volume of parallel work increases, the gap between the assumed state of integration contracts and their actual state widens faster than integration testing can close it. The work proceeds on assumptions that may be silently incorrect. Static typing prevents this structurally. The type system is not only a quality mechanism within a project; it is a coherence mechanism across projects.

*The empirical basis for this claim is examined in Part 5 of this series, which analyses GitHub history and integration evolution across a suite of five related systems developed concurrently in this model. The argument is introduced here as a structural claim; Part 5 will test it against evidence.*

**The cold-read problem.** One property of LLM-first development has no parallel in human development: the LLM begins every session without memory of previous ones. A human developer carries context between sessions. An LLM works from what is in the code. The quality of what the LLM can reconstruct from a cold read of the codebase determines how accurately and efficiently subsequent sessions proceed.

A statically typed codebase with explicit data contracts, compiler-enforced interfaces, and well-named record types is substantially more legible in a cold read than a dynamically typed one where structure must be inferred from usage. The type system serves, in this context, as a continuity mechanism — the means by which architectural intent persists across the session boundary that LLMs cannot bridge through memory. This is a property of statically typed languages that has no direct equivalent in human development, where memory provides continuity independently of the code. It is, consequently, an advantage that does not appear in conventional comparisons between Java and Python.

---

## 5. Where Python Remains the Right Choice

An argument that does not acknowledge the limits of its own applicability is not an argument — it is advocacy. Python has genuine advantages that this article would be dishonest to minimise, and they belong on the record clearly.

**The data science and machine learning ecosystem is a real and substantial advantage.** PyTorch, TensorFlow, JAX, Hugging Face Transformers, NumPy, SciPy, Pandas, scikit-learn, matplotlib, seaborn — these libraries represent decades of accumulated engineering, are maintained by large communities and well-resourced organisations, and have no Java equivalents of comparable breadth, depth, or production maturity. If you are training machine learning models, conducting statistical research, building data pipelines for scientific computing, or doing any work that sits in the domain these libraries serve, Python is the correct choice today. The argument in this article does not apply to that work. It applies to the class of work — application development, backend services, system integration — where these libraries are not the primary constraint.

**The exploration workflow is genuinely different.** Jupyter notebooks allow a mode of working — run a cell, inspect the output, modify the hypothesis, rerun — that serves data exploration and model experimentation in a way that compiled languages do not replicate today. JShell provides a Java REPL; Java Jupyter kernels exist. Neither constitutes a comparable workflow for the kind of iterative, output-inspecting work that data scientists actually do. This advantage is primarily a human one — LLMs do not benefit from the REPL in the way a human developer does — but the human is still present in the loop, and for this class of work, the human's exploration workflow matters.

**For small scripts and automation, the Java overhead is real.** A Python script that processes a CSV file, calls an API, and writes output can be written in twenty lines without a project structure, a build tool, or a package declaration. The equivalent Java requires a Maven project, a main class, dependency management, and compilation before it runs. For genuinely small, short-lived automation tasks, the startup cost of a Java project is disproportionate to the work being done. Python wins here, and this holds even for LLM-first development — the LLM still has to generate and manage the project scaffolding, and for a single-file script the overhead is unjustified.

**The ecosystem argument has inertia beyond its technical basis.** Even if Java's technical gaps close — as Part 4 of this series argues they are doing — the Python scientific computing ecosystem will not migrate quickly. The tools are built in Python, the tutorials are written in Python, the researchers who create and extend these libraries know Python. Cultural and ecosystem inertia responds to capability changes on a timescale of years to decades, not months. Anyone making framework decisions today should account for where the ecosystem is, not only where it is heading.

**Where this leaves the argument.** The case for Java in LLM-first development is strongest for the work that most LLM-first development currently involves: backend services, REST APIs, business logic, system integration, and the class of application code that is not primarily scientific computing. This is a large and growing domain. It is not the whole of software development. The honest scope of the argument is: *for production application development without primary scientific computing requirements, Java and Quarkus are the better choice when the primary implementer is a large language model, and the conventional case for Python as default does not hold up under examination.* Outside that scope, Python's advantages remain real, and this article makes no claim against them.

---

## 6. The Bias in the Conversation

The preceding sections have argued that the Python default is anthropocentric — that it rests on assumptions about human developer ergonomics that do not transfer to large language models. What has not yet been examined is how that bias manifests in practice: not in the abstract, but in an actual conversation between a human architect and the LLM that helped build the system this article describes.

When asked to explain the original Python recommendation, the response cited faster prototyping, lighter syntax, and easier iteration — the standard account. When pressed specifically on whether those advantages transferred to a large language model doing the implementation, the argument dissolved. Prototyping speed in Python is a function of reduced typing effort, REPL-driven iteration, and developer familiarity. None of those properties apply to a system that generates text. The LLM had produced a justification that was fluent, internally consistent, and inapplicable. The properties it cited belonged to human developers. It had not noticed the substitution.

The error has a specific structure: an inherited assumption presented as a reasoned conclusion. The training data that shaped the response was produced by human developers, for human developers, reflecting human constraints. When asked to reason about framework selection, the LLM retrieved that prior and applied it without examining whether the conditions that generated it were present in this case. They were not.

**What this means in practice.** An LLM recommending a framework is not performing an objective analysis of your project's requirements against available options. It is producing output shaped by the distribution of its training data and the assumptions embedded in the discourse that training data reflects. The recommendation will sound considered. It will be expressed with appropriate hedges and caveats. The fluency of the output and the validity of the reasoning are independent variables.

The corrective is not scepticism toward LLM recommendations in general. It is a specific challenge: *ask the LLM to justify the recommendation in terms of the actual implementer.* If the justification relies on developer ergonomics — typing speed, REPL iteration, syntax familiarity — ask whether those properties apply when the developer is the LLM itself. That single question, in the conversation that produced this article, was sufficient to expose the assumption and correct the reasoning.

This is not a failure specific to this system or this exchange. It is a property of how large language models carry and reproduce inherited assumptions — and evidence that those assumptions are worth examining explicitly rather than accepting as the output of a considered judgment. The form of a considered judgment and the substance of one are not the same thing.

---

## 7. A Decision Framework

The argument in this article can be reduced to a single question that should precede any framework selection for a new project: *who is writing the implementation?*

If the answer is a human developer, the conventional criteria apply. Language familiarity, team expertise, ecosystem fit, hiring pool, existing infrastructure — these are all legitimate inputs, and the relative weight given to Python or Java should reflect the specific constraints of the team and project. This article makes no claim against that reasoning when it is applied to the case it was designed for.

If the answer is a large language model — or a combination of LLM and human in which the LLM authors the bulk of the implementation — the framework selection criteria shift. The following questions replace or substantially outweigh the conventional ones:

**Does the framework enforce structural contracts at compile time?** A framework whose errors surface at runtime rather than at compile time transfers error detection cost to the debugging cycle, where LLM reasoning degrades with each iteration. Static typing is not a preference in this context — it is a mechanism for catching errors before the debugging cycle begins.

**Can the LLM reconstruct the system's intent from a cold read of the code?** Every LLM session begins without memory of previous ones. The code must carry the context that a human developer would carry in their head. Explicit type declarations, self-documenting record types, and compiler-enforced interfaces make the code legible across the session boundary. Implicit structure does not.

**Does the deployment target impose constraints that the framework must meet?** Bundling, startup time, runtime dependencies, and distribution format are determined by where the system runs, not by the language's abstract properties. In the Sparge case, Electron desktop embedding eliminated Python as a viable option independently of any argument about LLM ergonomics. Deployment constraints should be evaluated first, before language preference enters the discussion.

**Is the work scientific computing or data exploration?** If yes, Python's ecosystem advantage is real and the arguments in this article do not outweigh it. The scope of the Java recommendation is production application development — backend services, REST APIs, system integration, business logic. That scope is large. It is not universal.

**Will multiple systems develop concurrently and integrate?** If yes, the value of static typing compounds. Integration contracts expressed as compiler-enforced types provide coherence guarantees across concurrent development efforts that conventions and documentation cannot. The larger the integration surface, the more this matters.

---

Applying these questions to the Sparge project retrospectively: the deployment target imposed a hard constraint; the system was application code with no scientific computing requirements; multiple related systems were under concurrent development. On every criterion, Java was the correct answer before any argument about LLM ergonomics was made. The LLM recommended Python regardless.

That is the case for examining the default. Not that Python is wrong. That the default is untested, and testing it is cheap.

*Technical readers: additional arguments supporting the case for Java in LLM-first development are presented in the appendix below, with cross-references to the relevant sections above.*

---

## Appendix: Further Arguments for the Technical Reader

*The following arguments support the main thesis but are more technical in nature. They are presented here for readers who want to examine the evidence more closely. Non-technical readers who have followed the main argument above need not continue.*

---

### A1 — Refactoring Completeness

When an LLM refactors Java code — renames a method, changes a record field, restructures a package — the compiler validates that the refactoring is complete. Every call site that was not updated fails to compile. The LLM receives an exhaustive, precise list of what remains to be fixed.

In Python, a renamed function may leave call sites that still resolve through duck typing or dynamic dispatch, appearing correct until runtime reveals the breakage. The refactoring looks complete. It is not. The failure manifests later, in a context further removed from the cause.

For LLM-first development where refactoring is frequent — the LLM improving its previous work, the specification evolving, new requirements emerging — this structural completeness guarantee reduces the rate of silent regressions. It is not an advantage that appears in static comparisons between the languages; it appears when the code changes, which in LLM-first development is continuously.

---

### A2 — Virtual Threads and Concurrency Simplicity

Java 21's Project Loom virtual threads allow concurrent server code to be written with simple blocking idioms. The LLM generates straightforward sequential code — read a file, call an API, return a result — and the runtime scales it correctly without the LLM needing to reason about thread pools, async callbacks, or event loops.

Through Python 3.12, the GIL (Global Interpreter Lock) prevented true parallelism within a single process, requiring either the `asyncio` model — which demands that the LLM reason about coroutine semantics throughout the codebase — or multiprocessing, which introduces its own complexity around shared state and serialisation. Python 3.13 introduced free-threaded builds (PEP 703) that remove the GIL and allow true multi-threaded parallelism as an official CPython release. This is a genuine and significant development. Current caveats: free-threaded mode is opt-in (requiring a specifically compiled CPython variant), C extension compatibility is incomplete across third-party packages, and the feature is still stabilising toward the default. Python 3.14 is expected to mature this further. The `asyncio` model remains the dominant pattern for I/O-bound concurrency in Python today; free-threading specifically targets CPU-bound parallelism. The gap between Python and Java's virtual thread model is therefore narrowing, on a concrete timeline, from a direction that one year ago would not have been predicted.

For LLMs generating server code, the virtual thread model is both simpler to produce correctly and easier to verify in review. The correctness property that matters — this code handles concurrent requests without shared state corruption — is enforced by the runtime rather than requiring the LLM to reason about concurrency explicitly in every implementation decision.

---

### A3 — OpenAPI as Machine-Verifiable Specification

Quarkus generates an OpenAPI specification directly from JAX-RS annotations. The implementation and the specification cannot diverge: the annotations are both the code and the spec, and both are machine-readable.

In the design spec-led model, the OpenAPI document can serve as the integration contract between systems. When System A's API is annotated correctly, System B's type-safe REST client — also generated from the same spec — is guaranteed to speak the same contract. A change to System A's endpoint signature propagates as a compilation failure in System B's client, not as a runtime negotiation failure.

This closes the loop between the human's specification intent and the LLM's implementation in a way that is enforced by construction rather than by convention. It also means that the API documentation is always current — not a document that must be maintained separately from the code, but a property of the code itself.

---

### A4 — Error Message Precision and the Diagnosis Cycle

Java compiler errors are precise: file, line, column, what was expected, what was provided. A type mismatch at compile time gives the LLM exactly the information needed to fix the problem without diagnostic reasoning about what might have gone wrong.

Python runtime errors — particularly those involving type mismatches in duck-typed code, missing dictionary keys, or incorrect assumptions about object shape — can require substantial reasoning before the root cause is identifiable. The error message describes a symptom; the cause may be several layers removed.

This connects directly to the Debugging Decay Index finding cited in Section 2: LLM debugging effectiveness degrades by 60 to 80 percent within two to three iterations. The precision of the error signal determines how much of the LLM's available debugging capacity is consumed by diagnosis versus resolution. A precise compiler error requires little diagnosis. A cryptic runtime error may consume most of the capacity before the fix begins. Over many debugging cycles, this difference in error signal quality has a compounding effect on implementation velocity and token cost.

---

### A5 — Training Data Distribution: The Domain Caveat

The claim in Section 1 — that LLMs achieve 11.3 percentage points higher accuracy in Python than Java on benchmarks — requires a domain qualification.

This gap is concentrated in the scientific and algorithmic problem domains that dominate benchmark datasets such as HumanEval and MBPP. These domains reflect the data science corpus where Python's training data dominance is strongest. For web service code, REST API implementation, business logic, and the class of server-side application development this article primarily concerns, Java has substantial and high-quality training data — the entire Spring Boot, Java EE, and Jakarta EE corpus spans decades and is among the most thoroughly documented in existence.

The headline accuracy gap should not be read as a universal property. It is a domain-specific effect concentrated in precisely the areas where Python's ecosystem advantage is also strongest. In the application development domain, the gap is smaller than the aggregate statistics suggest, and the compiler-assisted correction mechanisms described in Section 2 further reduce its practical impact.

---

### A6 — The Positive Feedback Loop

The choice of programming language by LLMs has a self-reinforcing property that is worth making explicit.

LLMs trained on a corpus where Python dominates will generate Python code preferentially. That generated code — produced at scale by AI systems — accumulates in public repositories and becomes training data. The Python prior in the next generation of models strengthens, not because Python has become more suitable, but because it has become more prevalent in the training distribution.

This is a feedback loop. It does not correct for suitability; it amplifies whatever language happens to be in the current prior. If Python is not the correct choice for LLM-first application development — as this article argues — the feedback loop perpetuates an error at scale.

The call to LLM vendors in Part 4 of this series rests in part on this mechanism. Deliberate rebalancing of training data as Java's ecosystem closes its remaining gaps — rather than waiting for organic drift — would seed the inverse loop: better Java generation, more Java code in public repositories, stronger Java training data, better Java generation. The industry efficiency gains from this transition, if the cost argument in Section 2 holds, are material. Vendors have an interest in the outcome, not only the users of their systems.

---

## References

- *LLMs Love Python: A Study of LLMs' Bias for Programming Languages and Libraries* (2025) — arxiv.org/html/2503.17181v1
- *The Debugging Decay Index: Rethinking Debugging Strategies for Code LLMs* — arxiv.org/html/2506.18403v2
- *Helping LLMs Improve Code Generation Using Feedback from Testing and Static Analysis* — arxiv.org/html/2412.14841v1
- *Why AI is pushing developers toward typed languages* — github.blog/ai-and-ml/llms/why-ai-is-pushing-developers-toward-typed-languages/
- Mündler, He, Wang, Sen, Song, Vechev — *Type-Constrained Code Generation with Language Models* — PLDI 2025 (94% of compilation errors are type-related) — arxiv.org/abs/2504.09246
- *LLM Token Optimization: Cut Costs & Latency in 2026* — redis.io/blog/llm-token-optimization-speed-up-apps/
- *LLM Cost Optimization: 5 Levers to Cut API Spend 70-85%* — morphllm.com/llm-cost-optimization
- Project Panama (JEP 454) — stable Java 22 — openjdk.org/jeps/454
- Project Valhalla (JEP 401) — in development — openjdk.org/jeps/401
