import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AddPriceModal } from "./AddPriceModal";
import * as api from "./api";
import { ApiError } from "./api";
import { priceRow } from "./fixtures";

vi.mock("./api", async (orig) => ({
  ...(await orig<typeof import("./api")>()),
  createPrice: vi.fn(),
  fetchSuggestions: vi.fn(),
}));

const FROM = /Effective from/;
const IN = /Input price/;
const OUT = /^Output price/;
const CACHED = /Cached input price/;

async function fill(model: string, i: string, o: string, c: string) {
  const box = screen.getByRole("combobox", { name: "Model" });
  await userEvent.clear(box);
  if (model) await userEvent.type(box, model);
  for (const [re, v] of [
    [IN, i],
    [OUT, o],
    [CACHED, c],
  ] as const) {
    const el = screen.getByLabelText(re);
    await userEvent.clear(el);
    if (v) await userEvent.type(el, v);
  }
}

function setup(props: Partial<React.ComponentProps<typeof AddPriceModal>> = {}) {
  const onClose = vi.fn();
  const onSaved = vi.fn();
  render(<AddPriceModal open initialModel="" onClose={onClose} onSaved={onSaved} {...props} />);
  return { onClose, onSaved };
}

describe("AddPriceModal", () => {
  beforeEach(() => {
    vi.mocked(api.createPrice).mockReset();
    vi.mocked(api.fetchSuggestions).mockResolvedValue({ results: [] });
  });
  afterEach(() => vi.useRealTimers());

  it("shows title, fields and buttons with the exact labels", () => {
    setup();
    expect(screen.getByRole("dialog", { name: "Add New Price" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Model" })).toBeInTheDocument();
    expect(screen.getByLabelText("Input price (USD per 1M tokens)")).toBeInTheDocument();
    expect(screen.getByLabelText("Output price (USD per 1M tokens)")).toBeInTheDocument();
    expect(screen.getByLabelText("Cached input price (USD per 1M tokens)")).toBeInTheDocument();
    expect(screen.getByLabelText("Effective from")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
  });

  it("pre-fills the model", () => {
    setup({ initialModel: "gpt-z" });
    expect(screen.getByRole("combobox", { name: "Model" })).toHaveValue("gpt-z");
  });

  it("defaults effective-from to the next whole minute (never in the past)", () => {
    vi.useFakeTimers({ now: new Date(2026, 10, 12, 10, 30, 20) });
    setup();
    expect(screen.getByLabelText(FROM)).toHaveValue("2026-11-12T10:31");
  });

  it("requires a model and every price", async () => {
    setup();
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByText("Model is required.")).toBeInTheDocument();
    expect(screen.getAllByText("Enter a price.")).toHaveLength(3);
    expect(api.createPrice).not.toHaveBeenCalled();
  });

  it.each([
    ["-1", "Must be a number from 0 to 1000."],
    ["1000.01", "Must be a number from 0 to 1000."],
    ["abc", "Must be a number from 0 to 1000."],
    ["0.123456789", "No more than 8 decimal places."],
  ])("rejects input price %s", async (v, msg) => {
    setup();
    await fill("gpt-x", v, "1", "1");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByText(msg)).toBeInTheDocument();
    expect(api.createPrice).not.toHaveBeenCalled();
  });

  it("accepts the 0 and 1000 and 8 dp boundaries", async () => {
    vi.mocked(api.createPrice).mockResolvedValue(priceRow());
    const { onSaved } = setup();
    await fill("gpt-x", "0", "1000", "0.12345678");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onSaved).toHaveBeenCalled();
  });

  it("rejects an effective time more than 5s in the past, allows within grace", async () => {
    setup();
    await fill("gpt-x", "1", "1", "1");
    const from = screen.getByLabelText(FROM);
    await userEvent.clear(from);
    await userEvent.type(from, "2020-01-01T00:00");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByText("Effective from can't be in the past.")).toBeInTheDocument();
    expect(api.createPrice).not.toHaveBeenCalled();
  });

  it("shows the exact UTC timestamp confirmation line", async () => {
    setup();
    const from = screen.getByLabelText(FROM);
    await userEvent.clear(from);
    await userEvent.type(from, "2030-03-04T05:06");
    const utc = new Date("2030-03-04T05:06").toISOString().slice(0, 19).replace("T", " ");
    expect(screen.getByText(`This price will apply from ${utc} UTC.`)).toBeInTheDocument();
  });

  it("submits effective_from as a Z-suffixed UTC ISO string equal to the local conversion", async () => {
    vi.mocked(api.createPrice).mockResolvedValue(priceRow());
    const { onSaved } = setup();
    await fill(" gpt-x ", "1.5", "6", "0.75");
    const from = screen.getByLabelText(FROM);
    await userEvent.clear(from);
    await userEvent.type(from, "2030-03-04T05:06");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    const body = vi.mocked(api.createPrice).mock.calls[0][0];
    expect(body.effective_from.endsWith("Z")).toBe(true);
    expect(body.effective_from).toBe(new Date("2030-03-04T05:06").toISOString());
    expect(body).toMatchObject({
      model: "gpt-x",
      input_token_price_per_1m: "1.5",
      output_token_price_per_1m: "6",
      cached_token_price_per_1m: "0.75",
    });
    expect(onSaved).toHaveBeenCalledTimes(1);
  });

  it("shows a 409 detail at the top of the modal and stays open", async () => {
    vi.mocked(api.createPrice).mockRejectedValue(
      new ApiError(409, "A scheduled price already exists for this model. Delete it first.", {
        code: "scheduled_price_exists",
      }),
    );
    const { onSaved, onClose } = setup();
    await fill("gpt-x", "1", "1", "1");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("A scheduled price already exists for this model. Delete it first.");
    expect(onSaved).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("renders server field errors next to their fields", async () => {
    vi.mocked(api.createPrice).mockRejectedValue(
      new ApiError(400, "HTTP 400", {
        fields: { output_token_price_per_1m: ["Ensure this value is less than or equal to 1000."] },
      }),
    );
    setup();
    await fill("gpt-x", "1", "1", "1");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    const field = screen.getByLabelText(OUT);
    expect(await screen.findByText("Ensure this value is less than or equal to 1000.")).toBeInTheDocument();
    expect(field).toHaveAccessibleDescription(/less than or equal to 1000/);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("Cancel closes without saving", async () => {
    const { onClose } = setup();
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalled();
    expect(api.createPrice).not.toHaveBeenCalled();
  });
});

describe("AddPriceModal keyboard", () => {
  beforeEach(() => {
    vi.mocked(api.createPrice).mockReset();
    vi.mocked(api.fetchSuggestions).mockResolvedValue({ results: [] });
  });

  it("Enter in a price field submits a valid form exactly once", async () => {
    vi.mocked(api.createPrice).mockResolvedValue(priceRow());
    const { onSaved } = setup();
    await fill("gpt-x", "1", "2", "3");
    await userEvent.type(screen.getByLabelText(CACHED), "{Enter}");
    await vi.waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1));
    expect(api.createPrice).toHaveBeenCalledTimes(1);
  });
});
