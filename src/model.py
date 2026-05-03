import torch
import torch.nn as nn
from transformers import DistilBertModel


class PromptInjectionDetector(nn.Module):
    """
    Drop-in replacement for the original PromptInjectionDetector.

    Architecture is identical to original:
      DistilBERT → [CLS] → Dropout → Linear(768, num_labels)

    Key change vs original:
    ────────────────────────
    The attribute is named 'distilbert' (not 'bert' or 'distilbert').
    This matters because freeze_embeddings() in the E3 federated script
    accesses model.distilbert.embeddings to freeze before Opacus wraps
    the model. The original already used self.distilbert so this is
    fully backward-compatible.

    Interface is fully backward-compatible with original:
      - Same constructor signature (model_name, num_labels, dropout)
      - Same forward signature (input_ids, attention_mask) → logits
      - Same attribute names (self.distilbert, self.dropout, self.classifier)
    """

    def __init__(self,
                 model_name="distilbert-base-uncased",
                 num_labels=2,
                 dropout=0.1):
        super().__init__()
        self.distilbert = DistilBertModel.from_pretrained(model_name)
        self.dropout    = nn.Dropout(dropout)
        self.classifier = nn.Linear(self.distilbert.config.hidden_size, num_labels)

    def forward(self, input_ids, attention_mask):
        outputs      = self.distilbert(input_ids=input_ids,
                                       attention_mask=attention_mask)
        hidden_state = outputs.last_hidden_state[:, 0, :]  # CLS token
        hidden_state = self.dropout(hidden_state)
        logits       = self.classifier(hidden_state)
        return logits