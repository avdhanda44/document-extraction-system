import {
  AlertCircle,
  CheckCircle2,
  FileJson,
  FileUp,
  FileText,
  FolderOpen,
  Loader2,
  RefreshCcw,
  Save,
  ShieldCheck,
  UploadCloud,
} from "lucide-react";
import { useMemo, useState } from "react";

import { extractDocument, saveReviewedDocument } from "./api.js";

const emptyResult = null;

function FieldStatus({ result }) {
  if (!result) {
    return <span className="field-status neutral">Not checked</span>;
  }

  if (!result.valid) {
    return (
      <span className="field-status invalid">
        <AlertCircle size={14} />
        Invalid
      </span>
    );
  }

  if (result.warning) {
    return (
      <span className="field-status warning">
        <AlertCircle size={14} />
        Warning
      </span>
    );
  }

  return (
    <span className="field-status valid">
      <CheckCircle2 size={14} />
      Valid
    </span>
  );
}

function formatLabel(fieldName) {
  return fieldName
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function SummaryMetric({ label, value, tone }) {
  return (
    <div className={`metric ${tone || ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [result, setResult] = useState(emptyResult);
  const [fields, setFields] = useState({});
  const [isExtracting, setIsExtracting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [saveResult, setSaveResult] = useState(null);
  const [isDraggingFile, setIsDraggingFile] = useState(false);
  const [validationStale, setValidationStale] = useState(false);

  const validationSummary = result?.validation?.summary || {};
  const fieldResults = result?.validation?.field_results || {};
  const fieldEntries = useMemo(() => Object.entries(fields), [fields]);
  const rawText = result?.raw_text || "";

  const totalChecked = validationSummary.total_fields_checked || 0;
  const readyCount = fieldEntries.filter(([fieldName]) => fieldResults[fieldName]?.valid).length;
  const invalidCount = validationSummary.invalid_fields || 0;
  const warningCount = validationSummary.fields_with_warnings || 0;
  const hasValidationSchema = Boolean(result && totalChecked > 0);
  const canSaveReviewed = Boolean(result && result.document_type !== "unknown" && !isSaving);

  function setPendingFile(file) {
    if (!file) {
      return;
    }

    setSelectedFile(file);
    setError("");
    setSaveResult(null);
    setValidationStale(false);
  }

  function resetWorkspace() {
    setSelectedFile(null);
    setResult(emptyResult);
    setFields({});
    setError("");
    setSaveResult(null);
    setValidationStale(false);
    setIsDraggingFile(false);
  }

  async function handleExtract(event) {
    event.preventDefault();

    if (!selectedFile) {
      setError("Choose a document before extraction.");
      return;
    }

    setError("");
    setSaveResult(null);
    setIsExtracting(true);

    try {
      const data = await extractDocument(selectedFile);
      setResult(data);
      setFields(data.fields || {});
      setValidationStale(false);
    } catch (extractError) {
      setError(extractError.message);
    } finally {
      setIsExtracting(false);
    }
  }

  async function handleSaveReviewed() {
    if (!result) {
      return;
    }

    setError("");
    setSaveResult(null);
    setIsSaving(true);

    try {
      const data = await saveReviewedDocument({
        file_name: result.file_name,
        file_type: result.file_type,
        document_type: result.document_type,
        fields,
      });
      setSaveResult(data);
      setResult((currentResult) => ({
        ...currentResult,
        validation: data.validation,
      }));
      setFields(data.reviewed_output?.fields || fields);
      setValidationStale(false);
    } catch (saveError) {
      setError(saveError.message);
    } finally {
      setIsSaving(false);
    }
  }

  function updateField(fieldName, value) {
    setFields((currentFields) => ({
      ...currentFields,
      [fieldName]: value,
    }));
    setSaveResult(null);
    setValidationStale(true);
  }

  return (
    <main className="app-shell">
      <section className="workspace">
        <aside className="sidebar" aria-label="Document controls">
          <div className="brand-row">
            <div className="brand-mark">
              <FileJson size={22} />
            </div>
            <div>
              <h1>Extraction Review</h1>
              <p>Upload, verify, correct, and save structured document data.</p>
            </div>
          </div>

          <form className="upload-panel" onSubmit={handleExtract}>
            <label
              className={`drop-zone ${isDraggingFile ? "is-dragging" : ""} ${selectedFile ? "has-file" : ""}`}
              onDragEnter={(event) => {
                event.preventDefault();
                setIsDraggingFile(true);
              }}
              onDragOver={(event) => {
                event.preventDefault();
                setIsDraggingFile(true);
              }}
              onDragLeave={() => setIsDraggingFile(false)}
              onDrop={(event) => {
                event.preventDefault();
                setIsDraggingFile(false);
                setPendingFile(event.dataTransfer.files?.[0]);
              }}
            >
              <UploadCloud size={42} />
              <span className="upload-title">
                {selectedFile ? "File ready for extraction" : "Drop document here"}
              </span>
              <strong className="selected-file-name">
                {selectedFile ? selectedFile.name : "No file selected"}
              </strong>
              <span className="browse-pill">
                <FolderOpen size={16} />
                Browse files
              </span>
              <small>PDF, PNG, JPG, JPEG, or DOCX</small>
              <input
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.docx"
                onChange={(event) => {
                  setPendingFile(event.target.files?.[0]);
                }}
              />
            </label>

            <button className="primary-button" type="submit" disabled={isExtracting}>
              {isExtracting ? <Loader2 className="spin" size={18} /> : <FileUp size={18} />}
              {isExtracting ? "Extracting" : "Extract"}
            </button>
          </form>

          <div className="summary-panel">
            <div className="panel-heading">
              <ShieldCheck size={18} />
              <h2>Document</h2>
            </div>
            <dl>
              <div>
                <dt>File</dt>
                <dd>{result?.file_name || "Not extracted"}</dd>
              </div>
              <div>
                <dt>Type</dt>
                <dd>{result?.document_type || "-"}</dd>
              </div>
              <div>
                <dt>Confidence</dt>
                <dd>{result ? `${result.confidence_percent}%` : "-"}</dd>
              </div>
              <div>
                <dt>Engine</dt>
                <dd>{result?.extraction_engine || "-"}</dd>
              </div>
              <div>
                <dt>Method</dt>
                <dd>{result?.extraction_method || "-"}</dd>
              </div>
              <div>
                <dt>Original upload</dt>
                <dd>{result?.uploaded_file_deleted ? "Deleted after extraction" : "-"}</dd>
              </div>
            </dl>
          </div>

          <button className="ghost-button" type="button" onClick={resetWorkspace}>
            <RefreshCcw size={17} />
            New document
          </button>
        </aside>

        <section className="review-surface" aria-label="Field review">
          <header className="review-header">
            <div>
              <h2>Review Fields</h2>
              <p>Correct extracted values before saving the reviewed JSON.</p>
            </div>
            <button
              className="save-button"
              type="button"
              onClick={handleSaveReviewed}
              disabled={!canSaveReviewed}
            >
              {isSaving ? <Loader2 className="spin" size={18} /> : <Save size={18} />}
              {isSaving ? "Saving" : "Save reviewed"}
            </button>
          </header>

          {error && (
            <div className="notice error">
              <AlertCircle size={18} />
              {error}
            </div>
          )}

          {saveResult && (
            <div className="notice success">
              <CheckCircle2 size={18} />
              Reviewed JSON saved at {saveResult.output_path}
            </div>
          )}

          {result?.document_type === "unknown" && (
            <div className="notice warning">
              <AlertCircle size={18} />
              No document schema matched this file, so field validation cannot run yet. The raw
              text is still available for inspection.
            </div>
          )}

          {validationStale && (
            <div className="notice info">
              <AlertCircle size={18} />
              Field values changed. Save reviewed JSON to re-run validation.
            </div>
          )}

          <div className="metrics-row">
            <SummaryMetric label="Checked" value={totalChecked} />
            <SummaryMetric label="Valid" value={hasValidationSchema ? readyCount : "-"} tone="good" />
            <SummaryMetric label="Invalid" value={hasValidationSchema ? invalidCount : "-"} tone={invalidCount ? "bad" : ""} />
            <SummaryMetric label="Warnings" value={hasValidationSchema ? warningCount : "-"} tone={warningCount ? "warn" : ""} />
          </div>

          {!result ? (
            <div className="empty-state">
              <FileUp size={38} />
              <h3>No extraction yet</h3>
              <p>Select a document and run extraction to populate the review form.</p>
            </div>
          ) : (
            <div className="result-layout">
              {fieldEntries.length > 0 ? (
                <div className="field-grid">
                  {fieldEntries.map(([fieldName, value]) => {
                    const validation = fieldResults[fieldName];
                    const isInvalid = validation && !validation.valid;

                    return (
                      <label className={`field-row ${isInvalid ? "has-error" : ""}`} key={fieldName}>
                        <span className="field-topline">
                          <span className="field-name">{formatLabel(fieldName)}</span>
                          <FieldStatus result={validation} />
                        </span>
                        <textarea
                          value={Array.isArray(value) ? value.join("\n") : String(value ?? "")}
                          onChange={(event) => updateField(fieldName, event.target.value)}
                          rows={fieldName.includes("address") ? 4 : 2}
                        />
                        {(validation?.error || validation?.warning) && (
                          <small className="field-message">
                            {validation.error || validation.warning}
                          </small>
                        )}
                      </label>
                    );
                  })}
                </div>
              ) : (
                <div className="empty-state compact">
                  <AlertCircle size={34} />
                  <h3>No structured fields found</h3>
                  <p>Use the extracted text panel to inspect what OCR read from the document.</p>
                </div>
              )}

              <section className="raw-text-panel" aria-label="Raw extracted text">
                <div className="raw-text-header">
                  <FileText size={18} />
                  <div>
                    <h3>Extracted Text</h3>
                    <p>{result.extraction_engine} · {result.extraction_method}</p>
                  </div>
                </div>
                <pre>{rawText || "No raw text returned by the extractor."}</pre>
              </section>
            </div>
          )}
        </section>
      </section>
    </main>
  );
}
