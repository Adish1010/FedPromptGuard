import torch
from torch.utils.data import Dataset
from transformers import DistilBertTokenizerFast
import pandas as pd

# Tokenizer loaded once at module level — never re-downloaded per instance
_TOKENIZER = None

def _get_tokenizer(tokenizer_name="distilbert-base-uncased"):
    global _TOKENIZER
    if _TOKENIZER is None:
        _TOKENIZER = DistilBertTokenizerFast.from_pretrained(tokenizer_name)
    return _TOKENIZER


class PromptDataset(Dataset):
    """
    Drop-in replacement for the original PromptDataset.
    
    Key changes vs original:
    ─────────────────────────
    1. Pre-tokenises all samples at __init__ time (not per __getitem__ call).
       Original tokenised inside __getitem__ which caused:
         - Opacus collator dtype probe bug (squeeze timing issue)
         - Extreme slowness (tokenizer called once per sample per epoch)
         - Tokenizer re-downloaded on every PromptDataset() instantiation
    
    2. Uses DistilBertTokenizerFast (same vocab, 5x faster than slow version).
    
    3. Module-level tokenizer singleton — shared across all PromptDataset
       instances in the process, never re-downloaded.
    
    4. Accepts optional max_samples + seed for stratified downsampling
       (used by E3 federated loop; ignored by E1/E4 which pass full paths).
    
    5. __getitem__ returns pre-built tensors — no tokenizer call at access time.
       This is what Opacus requires for correct per-sample gradient computation.
    
    Interface is fully backward-compatible with original:
      - Same constructor signature (csv_path, tokenizer_name, max_length)
      - Same __getitem__ keys: input_ids, attention_mask, label
      - Same print statements on load
    """

    def __init__(self,
                 csv_path,
                 tokenizer_name="distilbert-base-uncased",
                 max_length=128,
                 max_samples=None,
                 seed=42):

        df = pd.read_csv(csv_path)

        # Validate columns (same assertions as original)
        assert "text"  in df.columns, "CSV must have a text column"
        assert "label" in df.columns, "CSV must have a label column"

        df = df.dropna(subset=["text", "label"]).reset_index(drop=True)
        df["label"] = df["label"].astype(int)

        # Optional stratified downsampling (for federated clients)
        if max_samples is not None and len(df) > max_samples:
            df = (df.groupby("label", group_keys=False)
                    .apply(lambda x: x.sample(
                        int(max_samples * len(x) / len(df)),
                        random_state=seed))
                    .reset_index(drop=True))

        # Same print format as original
        print(f"Loaded {len(df):,} samples from {csv_path}")
        print(f"  Malicious: {df['label'].sum():,} ({df['label'].mean()*100:.1f}%)")

        tokenizer = _get_tokenizer(tokenizer_name)

        # Pre-tokenise everything at once — O(N) total, not O(N) per epoch
        enc = tokenizer(
            df["text"].tolist(),
            max_length=max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )

        # Store as torch.long tensors — correct dtype, no squeeze needed in __getitem__
        self.input_ids      = enc["input_ids"].long()       # shape (N, max_length)
        self.attention_mask = enc["attention_mask"].long()  # shape (N, max_length)
        self.labels         = torch.tensor(df["label"].tolist(), dtype=torch.long)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        # Returns pre-built tensors — no tokenizer call here
        return {
            "input_ids":      self.input_ids[idx],       # shape (max_length,) torch.long
            "attention_mask": self.attention_mask[idx],  # shape (max_length,) torch.long
            "label":          self.labels[idx],          # scalar torch.long
        }