import {
  AlertCircle,
  CheckCircle2,
  Clipboard,
  Download,
  FileJson,
  FileText,
  FileUp,
  FolderOpen,
  Loader2,
  RefreshCcw,
  RotateCcw,
  Save,
  Search,
  ShieldCheck,
  UploadCloud,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { extractDocument, saveReviewedDocument } from "./api.js";

const emptyResult = null;

const groupDefinitions = [
  {
    title: "Identity",
    matches: ["name", "employee", "aadhaar", "pan_number", "gender", "relationship", "father", "husband", "care_of"],
  },
  {
    title: "Dates",
    matches: ["date", "birth", "joining", "opened", "issue", "year"],
  },
  {
    title: "Address",
    matches: ["address", "pincode", "city", "state"],
  },
  {
    title: "Bank",
    matches: ["bank", "branch", "ifsc", "micr", "account", "cif", "mop", "nom", "phone", "email"],
  },
  {
    title: "Invoice",
    matches: ["company", "receipt", "subtotal", "tax", "discount", "total", "currency", "source"],
  },
  {
    title: "Review",
    matches: ["signature", "continuation", "stamp", "vid", "mobile"],
  },
];

const aadhaarFrontFields = new Set([
  "aadhaar_number",
  "vid",
  "name",
  "hindi_name",
  "date_of_birth",
  "year_of_birth",
  "gender",
]);

const aadhaarBackFields = new Set([
  "aadhaar_number",
  "vid",
  "relationship_label",
  "care_of",
  "father_name",
  "husband_name",
  "hindi_relationship_label",
  "hindi_care_of",
  "hindi_father_name",
  "hindi_husband_name",
  "address",
  "hindi_address",
  "hindi_address_lines",
  "pincode",
]);

const documentDisplayFields = {
  aadhaar_front: aadhaarFrontFields,
  aadhaar_back: aadhaarBackFields,
  aadhaar_full: new Set([...aadhaarFrontFields, ...aadhaarBackFields]),
};

function FieldStatus({ result, edited }) {
  if (edited) {
    return <span className="field-status edited">Edited</span>;
  }

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

function getFieldGroup(fieldName) {
  const normalizedName = fieldName.toLowerCase();
  const group = groupDefinitions.find((definition) =>
    definition.matches.some((match) => normalizedName.includes(match)),
  );

  return group?.title || "Other";
}

function buildGroupedFields(fieldEntries) {
  const groups = new Map();

  for (const entry of fieldEntries) {
    const groupName = getFieldGroup(entry[0]);
    const fields = groups.get(groupName) || [];
    fields.push(entry);
    groups.set(groupName, fields);
  }

  return [
    ...groupDefinitions
      .map((definition) => [definition.title, groups.get(definition.title)])
      .filter(([, fields]) => fields?.length),
    ...Array.from(groups.entries()).filter(
      ([groupName]) => !groupDefinitions.some((definition) => definition.title === groupName),
    ),
  ];
}

function hasDisplayValue(value) {
  if (Array.isArray(value)) {
    return value.length > 0;
  }

  return String(value ?? "").trim() !== "";
}

function getDisplayFieldEntries(fieldEntries, documentType) {
  const allowedFields = documentDisplayFields[documentType];

  if (!allowedFields) {
    return fieldEntries;
  }

  return fieldEntries.filter(([fieldName, value]) => {
    if (allowedFields.has(fieldName)) {
      return true;
    }

    return hasDisplayValue(value);
  });
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function HighlightedRawText({ text, query }) {
  if (!query.trim()) {
    return text || "No raw text returned by the extractor.";
  }

  const pattern = new RegExp(`(${escapeRegExp(query.trim())})`, "gi");
  const parts = (text || "").split(pattern);

  return parts.map((part, index) =>
    part.toLowerCase() === query.trim().toLowerCase() ? (
      <mark key={`${part}-${index}`}>{part}</mark>
    ) : (
      <span key={`${part}-${index}`}>{part}</span>
    ),
  );
}

function makeReviewedJson(result, fields) {
  return {
    reviewed_output: {
      file_name: result.file_name,
      file_type: result.file_type,
      document_type: result.document_type,
      confidence_percent: result.confidence_percent,
      confidence_level: result.confidence_level,
      fields,
    },
    validation: result.validation,
    extraction: {
      engine: result.extraction_engine,
      method: result.extraction_method,
      attempts: result.extraction_attempts || [],
    },
  };
}

function DocumentPreview({ file, previewUrl }) {
  if (!file || !previewUrl) {
    return (
      <div className="document-preview empty-preview">
        <FileText size={24} />
        <span>No document preview</span>
      </div>
    );
  }

  if (file.type.startsWith("image/")) {
    return (
      <div className="document-preview">
        <img src={previewUrl} alt={file.name} />
      </div>
    );
  }

  if (file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf")) {
    return (
      <div className="document-preview">
        <iframe src={previewUrl} title={file.name} />
      </div>
    );
  }

  return (
    <div className="document-preview empty-preview">
      <FileText size={24} />
      <span>{file.name}</span>
      <small>Preview is available for PDF and image files.</small>
    </div>
  );
}

export default function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [result, setResult] = useState(emptyResult);
  const [fields, setFields] = useState({});
  const [originalFields, setOriginalFields] = useState({});
  const [isExtracting, setIsExtracting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [saveResult, setSaveResult] = useState(null);
  const [isDraggingFile, setIsDraggingFile] = useState(false);
  const [validationStale, setValidationStale] = useState(false);
  const [rawSearch, setRawSearch] = useState("");
  const [copiedRaw, setCopiedRaw] = useState(false);
  const [previewUrl, setPreviewUrl] = useState("");

  const validationSummary = result?.validation?.summary || {};
  const fieldResults = result?.validation?.field_results || {};
  const fieldEntries = useMemo(() => Object.entries(fields), [fields]);
  const displayFieldEntries = useMemo(
    () => getDisplayFieldEntries(fieldEntries, result?.document_type),
    [fieldEntries, result?.document_type],
  );
  const groupedFields = useMemo(() => buildGroupedFields(displayFieldEntries), [displayFieldEntries]);
  const rawText = result?.raw_text || "";
  const editedFields = useMemo(() => {
    const edited = new Set();

    for (const [fieldName, value] of fieldEntries) {
      if (String(value ?? "") !== String(originalFields[fieldName] ?? "")) {
        edited.add(fieldName);
      }
    }

    return edited;
  }, [fieldEntries, originalFields]);
  const reviewFields = useMemo(
    () =>
      displayFieldEntries.filter(([fieldName]) => {
        const validation = fieldResults[fieldName];
        return editedFields.has(fieldName) || (validation && (!validation.valid || validation.warning));
      }),
    [displayFieldEntries, editedFields, fieldResults],
  );

  const totalChecked = displayFieldEntries.length || validationSummary.total_fields_checked || 0;
  const readyCount = displayFieldEntries.filter(([fieldName]) => fieldResults[fieldName]?.valid).length;
  const invalidCount = displayFieldEntries.filter(([fieldName]) => fieldResults[fieldName] && !fieldResults[fieldName].valid).length;
  const warningCount = displayFieldEntries.filter(([fieldName]) => fieldResults[fieldName]?.warning).length;
  const hasValidationSchema = Boolean(result && totalChecked > 0);
  const canSaveReviewed = Boolean(result && result.document_type !== "unknown" && !isSaving);
  const confidence = Number(result?.confidence_percent || 0);

  useEffect(() => {
    if (!selectedFile) {
      setPreviewUrl("");
      return undefined;
    }

    const nextPreviewUrl = URL.createObjectURL(selectedFile);
    setPreviewUrl(nextPreviewUrl);

    return () => URL.revokeObjectURL(nextPreviewUrl);
  }, [selectedFile]);

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
    setOriginalFields({});
    setError("");
    setSaveResult(null);
    setValidationStale(false);
    setIsDraggingFile(false);
    setRawSearch("");
    setCopiedRaw(false);
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
      const extractedFields = data.fields || {};
      setResult(data);
      setFields(extractedFields);
      setOriginalFields(extractedFields);
      setValidationStale(false);
      setRawSearch("");
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
      const reviewedFields = data.reviewed_output?.fields || fields;
      setSaveResult(data);
      setResult((currentResult) => ({
        ...currentResult,
        validation: data.validation,
      }));
      setFields(reviewedFields);
      setOriginalFields(reviewedFields);
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

  function resetField(fieldName) {
    setFields((currentFields) => ({
      ...currentFields,
      [fieldName]: originalFields[fieldName] ?? "",
    }));
    setSaveResult(null);
    setValidationStale(true);
  }

  function resetAllFields() {
    setFields(originalFields);
    setSaveResult(null);
    setValidationStale(false);
  }

  function downloadReviewedJson() {
    if (!result) {
      return;
    }

    const reviewedJson = makeReviewedJson(result, fields);
    const blob = new Blob([JSON.stringify(reviewedJson, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    const fileStem = result.file_name?.replace(/\.[^.]+$/, "") || "reviewed_document";
    anchor.href = url;
    anchor.download = `${fileStem}_reviewed.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function copyRawText() {
    if (!rawText) {
      return;
    }

    await navigator.clipboard.writeText(rawText);
    setCopiedRaw(true);
    window.setTimeout(() => setCopiedRaw(false), 1400);
  }

  function renderField(fieldName, value) {
    const validation = fieldResults[fieldName];
    const isInvalid = validation && !validation.valid;
    const isEdited = editedFields.has(fieldName);

    return (
      <label className={`field-row ${isInvalid ? "has-error" : ""}`} key={fieldName}>
        <span className="field-topline">
          <span className="field-name">{formatLabel(fieldName)}</span>
          <FieldStatus result={validation} edited={isEdited} />
        </span>
        <textarea
          id={`field-${fieldName}`}
          value={Array.isArray(value) ? value.join("\n") : String(value ?? "")}
          onChange={(event) => updateField(fieldName, event.target.value)}
          rows={fieldName.includes("address") ? 4 : 2}
        />
        <span className="field-footer">
          <span className="field-message">{validation?.error || validation?.warning || ""}</span>
          {isEdited && (
            <button className="field-reset-button" type="button" onClick={() => resetField(fieldName)}>
              <RotateCcw size={13} />
              Reset
            </button>
          )}
        </span>
      </label>
    );
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
                <dd>
                  {result ? (
                    <span className="confidence-meter">
                      <span>{confidence}%</span>
                      <span className="confidence-track">
                        <span
                          className={`confidence-fill ${confidence >= 80 ? "good" : confidence >= 50 ? "warn" : "bad"}`}
                          style={{ width: `${Math.min(confidence, 100)}%` }}
                        />
                      </span>
                    </span>
                  ) : (
                    "-"
                  )}
                </dd>
              </div>
              <div>
                <dt>Engine</dt>
                <dd>{result?.extraction_engine || "-"}</dd>
              </div>
              <div>
                <dt>Method</dt>
                <dd>{result?.extraction_method || "-"}</dd>
              </div>
              {result?.extraction_attempts?.length > 1 && (
                <div>
                  <dt>Attempts</dt>
                  <dd>
                    {result.extraction_attempts
                      .map((attempt) => attempt.engine)
                      .join(" > ")}
                  </dd>
                </div>
              )}
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
            <div className="review-actions">
              <button
                className="secondary-button"
                type="button"
                onClick={resetAllFields}
                disabled={!result || editedFields.size === 0}
              >
                <RotateCcw size={18} />
                Reset edits
              </button>
              <button
                className="secondary-button"
                type="button"
                onClick={downloadReviewedJson}
                disabled={!result}
              >
                <Download size={18} />
                Download JSON
              </button>
              <button
                className="save-button"
                type="button"
                onClick={handleSaveReviewed}
                disabled={!canSaveReviewed}
              >
                {isSaving ? <Loader2 className="spin" size={18} /> : <Save size={18} />}
                {isSaving ? "Saving" : "Save reviewed"}
              </button>
            </div>
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
              <section className="raw-text-panel" aria-label="Raw extracted text">
                <div className="raw-text-header">
                  <FileText size={18} />
                  <div>
                    <h3>Document Evidence</h3>
                    <p>{result.extraction_engine} · {result.extraction_method}</p>
                  </div>
                </div>
                <DocumentPreview file={selectedFile} previewUrl={previewUrl} />
                <div className="raw-tools">
                  <label className="raw-search">
                    <Search size={15} />
                    <input
                      value={rawSearch}
                      onChange={(event) => setRawSearch(event.target.value)}
                      placeholder="Search text"
                    />
                  </label>
                  <button className="icon-text-button" type="button" onClick={copyRawText} disabled={!rawText}>
                    <Clipboard size={15} />
                    {copiedRaw ? "Copied" : "Copy"}
                  </button>
                </div>
                <pre>
                  <HighlightedRawText text={rawText} query={rawSearch} />
                </pre>
              </section>

              <section className="fields-panel" aria-label="Extracted fields">
                {reviewFields.length > 0 && (
                  <section className="needs-review-panel">
                    <div className="section-heading">
                      <AlertCircle size={17} />
                      <h3>Needs Review</h3>
                    </div>
                    <div className="review-chip-list">
                      {reviewFields.map(([fieldName]) => {
                        const validation = fieldResults[fieldName];
                        return (
                          <a className="review-chip" href={`#field-${fieldName}`} key={fieldName}>
                            <span>{formatLabel(fieldName)}</span>
                            <small>
                              {editedFields.has(fieldName)
                                ? "Edited"
                                : validation?.error || validation?.warning || "Review"}
                            </small>
                          </a>
                        );
                      })}
                    </div>
                  </section>
                )}

                {displayFieldEntries.length > 0 ? (
                  <div className="field-sections">
                    {groupedFields.map(([groupName, entries]) => (
                      <section className="field-section" key={groupName}>
                        <div className="section-heading">
                          <h3>{groupName}</h3>
                          <span>{entries.length}</span>
                        </div>
                        <div className="field-grid">
                          {entries.map(([fieldName, value]) => renderField(fieldName, value))}
                        </div>
                      </section>
                    ))}
                  </div>
                ) : (
                  <div className="empty-state compact">
                    <AlertCircle size={34} />
                    <h3>No structured fields found</h3>
                    <p>Use the extracted text panel to inspect what OCR read from the document.</p>
                  </div>
                )}
              </section>
            </div>
          )}
        </section>
      </section>
    </main>
  );
}
