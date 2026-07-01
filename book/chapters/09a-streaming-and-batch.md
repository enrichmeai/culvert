# Streaming and Batch: Choosing the Mode

One of the questions I get asked earliest and answer most often is: *should this be streaming or batch?* Teams reach for streaming because it sounds modern, then spend a year operating a real-time system to satisfy a report nobody reads before 9 a.m. So let me give you the framing I actually use — and the good news is that in Culvert the choice is smaller than it looks, because it lives at the *contract* level, not in your business logic.

## The same contracts serve both

A Culvert pipeline reads through a `Source`, transforms through `Transform`, and writes through a `Sink`. Those contracts (`data-pipeline-core-java/.../contracts/Source.java`, `Sink.java`, `Transform.java`; Python mirrors in `contracts/source.py`) say nothing about *when* records arrive. A `Source` yields records; whether it yields a bounded file this morning or an unbounded subscription forever is a property of the *adapter*, not the contract. That is the whole trick, and it is why the mode decision does not rewrite your transforms.

- **Batch**, on GCP, is a bounded read: `GcsBlobStore` (`data-pipeline-gcp-gcs`) hands you an object; the pipeline runs to completion and stops.
- **Streaming**, on GCP, is an unbounded read: `PubSubSource` (`data-pipeline-gcp-pubsub`) yields messages as they arrive; `PubSubSink` publishes them. The pipeline stays up.

Both flow through the *same* `Transform`. If you wrote your validation and mapping against the contract — as Culvert pushes you to — swapping a batch source for a streaming one does not touch it. `DataflowPipeline` (`data-pipeline-gcp-dataflow-java`) runs either bounded or unbounded graphs on the same Beam model.

## How to actually choose

I decide on four questions, in order:

1. **What does the consumer need?** If the downstream report, model, or decision is consumed daily, you need daily data. Latency you do not consume is latency you pay for and waste. Most enterprise data-to-BigQuery work is batch and should stay batch.
2. **How does the source produce?** A mainframe that drops a file at 02:00 is batch at the source; wrapping it in streaming buys you nothing but a standing bill. An event bus that emits continuously is streaming at the source; forcing it into a nightly batch loses the point.
3. **What is the cost curve?** Batch is cheap-per-run and idle the rest of the day. Streaming is a standing cost — workers up 24/7, per-message overhead. Culvert's `FinOpsSink` and the per-service cost trackers (Chapter [Cost and FinOps]) let you put a real number on both before you commit; do that, not a vibe.
4. **What is the failure model you can live with?** Batch fails a run and you re-run it — simple, auditable, a clean `run_id` per attempt. Streaming fails a *record* and you need dead-letter handling, watermarks, and replay. That operational weight is the real price of streaming, more than the compute.

## The honest default

Start batch. Move to streaming only when a question above forces it — a genuinely continuous source, or a consumer that genuinely needs sub-hour latency. The contract seam means that migration, when it comes, is an adapter swap and an execution-mode change, not a rewrite. That is exactly the position you want to be in: the decision stays reversible.

\begin{takeaways}
\textbf{Key takeaways}
\begin{itemize}
  \item In Culvert the batch-vs-streaming choice lives in the \emph{adapter} and execution mode, not the business logic — the same \texttt{Source}/\texttt{Sink}/\texttt{Transform} contracts serve both.
  \item GCP: batch = a bounded \texttt{GcsBlobStore} read; streaming = an unbounded \texttt{PubSubSource}. Both run on the same \texttt{DataflowPipeline}.
  \item Choose on consumer need, source shape, cost curve, and failure model — in that order. Latency you do not consume is wasted spend.
  \item Default to batch; move to streaming only when a real requirement forces it. The contract seam keeps that migration an adapter swap, not a rewrite.
\end{itemize}
\end{takeaways}

\newpage
