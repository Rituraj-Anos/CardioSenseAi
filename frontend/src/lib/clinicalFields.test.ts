import { describe, expect, it } from "vitest";
import { CLINICAL_FIELDS, DEMO_CONCERNING, DEMO_NORMAL } from "./clinicalFields";

// These encodings must match the backend's verified UCI mapping. Getting them
// wrong here silently feeds the model mislabelled categories — so we pin them.
function options(name: string) {
  const f = CLINICAL_FIELDS.find((x) => x.name === name);
  if (!f || f.kind !== "select") throw new Error(`no select field ${name}`);
  return Object.fromEntries(f.options.map((o) => [o.value, o.label]));
}

describe("clinical field encodings (verified against UCI)", () => {
  it("has all 13 features", () => {
    expect(CLINICAL_FIELDS).toHaveLength(13);
  });

  it("chest pain type maps values correctly", () => {
    const cp = options("cp");
    expect(cp[0]).toBe("Asymptomatic");
    expect(cp[3]).toBe("Typical angina");
  });

  it("resting ECG maps values correctly", () => {
    const r = options("restecg");
    expect(r[0]).toBe("Left ventricular hypertrophy");
    expect(r[1]).toBe("Normal");
    expect(r[2]).toBe("ST-T wave abnormality");
  });

  it("ST slope maps values correctly", () => {
    const s = options("slope");
    expect(s[0]).toBe("Downsloping");
    expect(s[2]).toBe("Upsloping");
  });

  it("thallium maps values correctly (2 = normal, 3 = reversible)", () => {
    const t = options("thal");
    expect(t[1]).toBe("Fixed defect");
    expect(t[2]).toBe("Normal");
    expect(t[3]).toBe("Reversible defect");
  });

  it("numeric fields carry physiological range bounds", () => {
    const bp = CLINICAL_FIELDS.find((f) => f.name === "trestbps");
    expect(bp?.kind).toBe("number");
    if (bp?.kind === "number") {
      expect(bp.min).toBeGreaterThanOrEqual(60);
      expect(bp.max).toBeLessThanOrEqual(260);
    }
  });

  it("demo presets cover every field", () => {
    for (const f of CLINICAL_FIELDS) {
      expect(DEMO_NORMAL[f.name]).toBeTypeOf("number");
      expect(DEMO_CONCERNING[f.name]).toBeTypeOf("number");
    }
  });
});
