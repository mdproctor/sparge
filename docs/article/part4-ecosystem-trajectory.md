# When the Machine Codes: Java's Ecosystem Trajectory and a Call to the Industry

**Part 4 of 5 — When the Machine Codes series**  
**Status:** Draft complete. Not yet published.

*Parts 1 through 3 of this series have argued that Java and Quarkus are better suited than Python for LLM-first development of production application software. This article addresses the strongest remaining objection to that argument, documents the trajectory on which it is being resolved, and ends with a call directed at the organisations best placed to accelerate that resolution.*

---

Parts 1 through 3 of this series were careful to limit their scope. The case for Java in LLM-first development was stated as applying to production application development — backend services, REST APIs, system integration, business logic — without primary scientific computing requirements. That limitation was not rhetorical modesty. It was an honest acknowledgement of where Python's advantages remain real and substantial.

This article examines those advantages directly: what they are, how large they currently are, what is happening to close them, and what — if the argument in this series is correct — the industry should do about it.

---

## 1. The Objection Stated Fairly

Python's data science and machine learning ecosystem is not an accident. It is the result of two decades of sustained investment by an enormous and productive community, backed by some of the most resource-rich organisations in technology.

PyTorch, TensorFlow, and JAX provide the foundations for training and running neural networks at scale. NumPy and SciPy provide the numerical computing primitives on which almost everything else is built. Pandas provides the data manipulation tools that make tabular data tractable. scikit-learn provides the classical machine learning algorithms that remain the workhorse of applied data science. The Hugging Face ecosystem provides the infrastructure through which the research community's models reach practitioners. matplotlib and seaborn provide the visualisation tools that make analysis communicable.

None of these libraries has a Java equivalent of comparable maturity, breadth, or community support. DJL (Deep Java Library) provides ML inference capabilities in Java and is actively maintained by Amazon. ONNX Runtime supports Java. Tribuo and Smile offer classical machine learning algorithms. These are real libraries doing real work. They are not the Python ecosystem. The gap is measured in years of development, thousands of contributors, and the accumulated weight of a community's conventions and expectations.

This is not a gap that closes with a language release. It reflects where the scientific computing community has historically built and continues to build. For organisations doing data science, statistical research, model training, or scientific computing, Python is the correct choice today. The arguments in this series do not change that, and this article does not claim that they should.

The segmentation model — data scientists use Python for exploration and research; Java dominates applied application development — is not a compromise. It is an accurate description of the current state of the field and a rational framework for language choice in most organisations today.

---

## 2. What Is Already Closed

The gap between Java and Python is not static. Two of its components have already been addressed — one completely, one substantially.

**Native library access — closed. Java 22, standard OpenJDK.**

Python's data science performance does not come from Python. NumPy's array operations run at C speed because NumPy is a Python wrapper around BLAS and LAPACK — linear algebra routines written in C and Fortran that have been optimised for decades. The Python code orchestrates; the C code computes.

Project Panama — the Foreign Function & Memory API, standardised as JEP 454 in Java 22 — allows Java to call C and Fortran code directly, without the JNI boilerplate that previously made this approach difficult. Java can now reach the same native foundations that Python's scientific libraries wrap. This is not a workaround or a preview feature: JEP 454 is stable, part of standard OpenJDK, and available to any Java 22 or later project without additional JVM configuration.

What Panama closes is the *technical* barrier to Java-native scientific computing libraries. What it does not close is the *ecosystem* barrier — the Python wrappers are mature, tested, and documented; the Java-native equivalents are emerging. Panama makes it possible to build the Java equivalent of NumPy. It does not provide it.

For production systems that consume pre-trained models rather than training them, the gap is already smaller. DJL (Deep Java Library) wraps PyTorch, TensorFlow, and MXNet for inference in Java. ONNX Runtime for Java runs models exported from any major training framework. For organisations building Java applications that need to serve predictions from ML models, viable solutions exist today.

**Language verbosity — substantially closed. Java 21 LTS and beyond.**

The mental model most people carry of Java as a verbose language was formed on Java 8 or earlier. That Java required `public static void main(String[] args)` for a hello-world program. It had no type inference, no records, no pattern matching, no text blocks. It is not the Java of 2025.

Java 16 introduced records — immutable data classes in a single line. Java 17 introduced sealed classes. Java 21 introduced pattern matching for switch, unnamed patterns, and virtual threads. Each of these reduces the ceremony required to express common patterns. The Java that LLMs generate today for a data contract — `record MdIssue(String check, String level, String detail) {}` — is three tokens more than a Python dataclass. The objection that Java is too verbose to be practical has not kept pace with the language's evolution.

But the verbosity argument deserves a sharper response than noting that Java has become less verbose. The argument in Part 2 of this series is that for LLMs specifically, the additional declarations are not a cost at all. The Python dict that saves five lines of declaration also withholds five lines of verified structural information from the next session — information the LLM must reconstruct by inference rather than read from the compiler-verified code. The verbosity *is* the specification. Removing it does not save work; it transfers the work from the type system to the reasoning process, where it is more expensive and less reliable. Java 25–26 reducing boilerplate further is welcome — but the case for static typing in LLM-first development was never primarily about verbosity reduction. It was about what the declarations contain.

Java 25 (September 2025, the next LTS release) is expected to bring unnamed classes and instance main methods, eliminating the boilerplate entry point for simple programs. Java 26 is likely to stabilise string templates. The trajectory is consistent and the direction is clear: the verbosity gap that was real in 2015 is narrow in 2025 and will be narrower still in 2026. For the kind of code LLMs generate — records, endpoints, service classes, test cases — it is already largely irrelevant.

---

## 3. What Is Closing

*[Technical detail — safe to skip]*

Two further gaps are on trajectories toward closure, with realistic timelines.

**Numerical performance — Project Valhalla, Java 25–28.**

The performance advantage of NumPy over equivalent Java code comes not only from calling C — which Panama now enables — but from memory layout. NumPy arrays store primitive values (doubles, integers) contiguously in memory, without object headers. This layout enables CPU cache efficiency that makes numerical computation fast. Java's object model, which wraps every primitive in a heap-allocated object when stored in a collection, has historically prevented this layout. A `List<Double>` in Java stores references to boxed `Double` objects, not contiguous doubles.

Project Valhalla's value classes (JEP 401) eliminate this constraint. Value classes are objects without identity — they can be stored inline in arrays and collections, contiguously in memory, without boxing overhead. This is the performance primitive that makes NumPy-class Java libraries structurally possible: an array of value-class objects can be laid out as packed primitives, just as a C array would be.

JEP 401 is targeting preview status in Java 25 (September 2025) or Java 26 (March 2026). Stable status is expected in Java 27 (September 2026) or Java 28 (March 2027). These are indicative timelines based on the standard six-month release cadence; features in preview have historically slipped by one release. The direction is not in doubt; the exact version carries appropriate uncertainty.

Once value classes are stable, the performance argument against Java-native scientific computing libraries dissolves. Libraries can be built that match NumPy's memory characteristics. The effort of building them remains — but the technical barrier no longer exists.

**Python interop — GraalVM and GraalPy.**

GraalVM Community Edition is open source and is the foundation of Quarkus native image compilation — already in production use across many organisations. Teams running Quarkus are already running GraalVM.

GraalPy — the Python implementation running on GraalVM's Truffle framework — allows Python code to execute within the JVM. This includes Python libraries: a Java application using GraalPy can call pandas, scikit-learn, or matplotlib without a process boundary. The data does not need to be serialised and sent between processes; it can be shared in memory.

GraalPy is not yet production-ready for complex scientific workloads. It runs many Python packages correctly; it does not run all of them at production scale with production reliability. The trajectory is real, the investment is active, and for teams already on GraalVM the path is shorter than it appears from the outside.

*[End technical detail]*

---

*The timeline diagram below summarises the six gap categories, features already shipped, features in preview, and the speculative trajectory to Java 28.*

![Java ecosystem gap timeline — When the Machine Codes series](article-java-timeline@2x.png)

---

## 4. What Remains Open

The honest accounting matters more than the optimistic projection.

Even after Panama is fully utilised, Valhalla stabilises, and GraalPy matures, the Python ecosystem will not relocate to Java. The tools will still be built in Python first. The tutorials will still teach Python. The researchers who build the libraries will still know Python, and their students will learn what their supervisors know. Cultural and ecosystem inertia responds to capability changes on a timescale measured in years to decades, not in release cycles.

This means the segmentation model — data scientists keep Python; Java dominates application development — will remain the practical reality for most organisations for the foreseeable future, even as technical barriers close. The convergence model — where Java becomes viable for the scientific exploration idiom itself — is a trajectory, not a scheduled event. It depends not only on Valhalla and GraalPy maturing, but on library authors choosing Java, educators teaching Java, and the research community adopting tools built in Java. None of those shifts happens quickly or automatically.

**The two models can coexist without contradiction.** For today, and for the next several years: segment. Use Python where the ecosystem advantage is real. Use Java where the application development arguments in Parts 1 through 3 apply. These are complementary recommendations, not competing ones. The data scientist training a model in Python and the engineer building the service that serves predictions from that model in Java are not in conflict — they are each using the right tool for their part of the work.

The convergence model is offered as a trajectory to watch, not a recommendation to act on prematurely. If and when Java-native scientific computing libraries reach production maturity, the case for segmentation weakens. Until then, it holds.

---

## 5. A Call to the Industry

The preceding sections have addressed the state of the Java ecosystem and its near-term trajectory. This section addresses something different: a dynamic in how LLMs choose frameworks that is independent of ecosystem state, and that requires deliberate intervention if it is to correct.

**The feedback loop.**

LLMs trained on a corpus where Python dominates will generate Python code preferentially. That generated code — produced at scale by AI systems across thousands of projects — accumulates in public repositories. Public repositories are training data. The Python prior in the next generation of models strengthens — not because Python has become more suitable, but because it has become more prevalent in the training distribution.

This is not a hypothetical mechanism. It is how language models work: the distribution of the training corpus shapes the distribution of the output, and the output, once published, shapes future training corpora. The dynamic is self-reinforcing. It does not correct for suitability; it amplifies prevalence. If the argument in this series is correct — that Python is not the right default for LLM-first application development — then the feedback loop is perpetuating an error at scale, and doing so faster as the volume of AI-generated code grows.

**What the call asks for.**

The organisations best placed to address this are LLM vendors — the teams responsible for training data curation, model evaluation, and the framework recommendations their systems make. The call is specific:

*In the application development domain — backend services, REST APIs, system integration — the evidence in this series suggests Java is already the better choice for LLM-first development.* This is a large domain. It is the domain where most enterprise software development happens. Rebalancing training data toward higher-quality Java for this domain does not require waiting for Valhalla to close the scientific computing gap. The gap that needs closing — in training data — is between Java's actual suitability for application development and its current representation in model behaviour.

As Project Panama enables Java-native scientific computing libraries and Project Valhalla removes the performance constraints that prevented them, training data should be rebalanced to reflect those changes — deliberately, rather than waiting years for organic drift to close the gap.

The alternative is allowing a training distribution that reflects the ecosystem of 2015 to shape framework recommendations in 2026 and beyond. The cost of that misalignment is measured in debug cycles, in token costs, in integration failures, and in the accumulated inefficiency of a development model that is using the wrong tool because no one examined the assumption.

**A note on what is already happening.**

The industry is not unaware of this dynamic. TypeScript's trajectory — surpassing both JavaScript and Python as GitHub's most-used language by contributor count in 2025, with 66 percent year-on-year growth — is partly explained by the same type-safety-for-LLM-code argument that this series makes for Java. Developers and LLM-assisted projects are gravitating toward languages where the type system catches errors that dynamic languages leave to runtime discovery. Java requires a similar deliberate correction specifically in the application development domain, where its advantages are already present and where the case for Python's default status has not been examined.

*The efficiency claims underlying this call — the token cost differential, the integration coherence advantage — are introduced in Part 2 of this series and will be tested empirically in Part 5, currently in preparation.*

---

## Closing

The argument of this series is complete in four parts. Part 1 identified where the Python default comes from and why it has not been examined. Part 2 argued for Java on grounds specific to LLM-first development. Part 3 documented what a migration from Python to Java reveals in practice. This article has acknowledged what Python's ecosystem advantages are, traced the trajectory on which they are being resolved, and named the feedback loop that makes deliberate action more valuable than waiting.

The case is not that Python is wrong. It is that the default is untested, the testing changes the answer for a significant class of work, and the industry has the means and the interest to act on that finding.

Part 5, forthcoming, will examine the same argument from a different angle: not a migration completed, but a suite of systems built from inception in the model described here — in parallel, at scale, with growing and changing APIs and the type system as the coherence mechanism. The empirical record of that work is the remaining evidence.

---

## References

- Project Panama (JEP 454) — stable Java 22 — openjdk.org/jeps/454
- Project Valhalla (JEP 401) — in development — openjdk.org/jeps/401
- Project Amber — openjdk.org/projects/amber/
- GraalVM Community Edition — graalvm.org
- GraalPy — github.com/oracle/graalpython
- DJL (Deep Java Library) — djl.ai
- ONNX Runtime for Java — onnxruntime.ai
- *Why AI is pushing developers toward typed languages* — github.blog/ai-and-ml/llms/why-ai-is-pushing-developers-toward-typed-languages/
- Java release schedule — 6-month cadence; Java 25 LTS (September 2025), Java 26 (March 2026), Java 27 (September 2026), Java 28 (March 2027)
