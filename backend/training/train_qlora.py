"""
QLoRA Fine-tuning Script for Sanjeevani
Base model: BioMistral-7B (Mistral-7B fine-tuned on PubMed)
Target: Medical Q&A with Indian health context

Hardware requirements:
  Minimum: 1x A10G (24GB VRAM) — fits comfortably
  Recommended: 1x A100 (40GB) for speed
  Estimated training time: ~4 hours on A10G for 10k examples

Run:
  pip install transformers datasets peft trl bitsandbytes accelerate wandb
  python training/train_qlora.py --config training/config.yaml
"""

import os
import json
import argparse
from dataclasses import dataclass, field
from typing import Optional

import torch
from datasets import load_dataset, Dataset
from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments,
)
from trl import SFTTrainer
import wandb


# ── Configuration ──────────────────────────────────────────────────────────────

@dataclass
class TrainingConfig:
    # Model
    base_model: str = "BioMistral/BioMistral-7B"
    output_dir: str = "./output/sanjeevani-biomistral-qlora"

    # Dataset
    dataset_path: str = "data/training/medical_qa.jsonl"
    val_split: float = 0.05

    # QLoRA
    lora_r: int = 64                    # rank — higher = more capacity, more VRAM
    lora_alpha: int = 16                 # scaling factor
    lora_dropout: float = 0.05
    target_modules: list = field(default_factory=lambda: [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj"
    ])

    # Quantization
    load_in_4bit: bool = True
    bnb_4bit_quant_type: str = "nf4"    # NF4 > FP4 for LLMs
    bnb_4bit_compute_dtype: str = "bfloat16"

    # Training
    num_epochs: int = 3
    per_device_train_batch_size: int = 4
    gradient_accumulation_steps: int = 4  # effective batch = 16
    learning_rate: float = 2e-4
    lr_scheduler_type: str = "cosine"
    warmup_ratio: float = 0.05
    max_seq_length: int = 2048
    weight_decay: float = 0.001
    optim: str = "paged_adamw_32bit"

    # Saving
    save_steps: int = 100
    eval_steps: int = 100
    logging_steps: int = 25
    save_total_limit: int = 3

    # W&B
    wandb_project: str = "sanjeevani"
    report_to: str = "wandb"


# ── Data formatting ────────────────────────────────────────────────────────────

PROMPT_TEMPLATE = """<s>[INST] You are Sanjeevani, a trusted medical information assistant.
Answer the following health question accurately and concisely.
Always recommend consulting a doctor for diagnosis or treatment.

Question: {question} [/INST]

{answer}</s>"""


def format_sample(sample: dict) -> str:
    return PROMPT_TEMPLATE.format(
        question=sample["question"].strip(),
        answer=sample["answer"].strip(),
    )


def load_medical_dataset(path: str, val_split: float = 0.05):
    """
    Load JSONL dataset with {question, answer, source} fields.
    
    Recommended sources to compile:
    - MedQuAD (National Library of Medicine)
    - HealthLine Q&A
    - Mayo Clinic FAQ
    - WHO health fact sheets
    - Custom Indian health context Q&As
    """
    data = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                item = json.loads(line)
                if item.get("question") and item.get("answer"):
                    data.append({"text": format_sample(item)})

    dataset = Dataset.from_list(data)
    split = dataset.train_test_split(test_size=val_split, seed=42)
    return split["train"], split["test"]


# ── Model setup ────────────────────────────────────────────────────────────────

def load_model_and_tokenizer(cfg: TrainingConfig):
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=cfg.load_in_4bit,
        bnb_4bit_quant_type=cfg.bnb_4bit_quant_type,
        bnb_4bit_compute_dtype=getattr(torch, cfg.bnb_4bit_compute_dtype),
        bnb_4bit_use_double_quant=True,   # nested quantization saves ~0.4 bits/param
    )

    model = AutoModelForCausalLM.from_pretrained(
        cfg.base_model,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    )
    model.config.use_cache = False
    model.config.pretraining_tp = 1

    tokenizer = AutoTokenizer.from_pretrained(cfg.base_model, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    return model, tokenizer


def apply_lora(model, cfg: TrainingConfig):
    model = prepare_model_for_kbit_training(model)
    lora_config = LoraConfig(
        r=cfg.lora_r,
        lora_alpha=cfg.lora_alpha,
        target_modules=cfg.target_modules,
        lora_dropout=cfg.lora_dropout,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    return model


# ── Training ──────────────────────────────────────────────────────────────────

def train(cfg: TrainingConfig):
    if cfg.report_to == "wandb" and os.getenv("WANDB_API_KEY"):
        wandb.init(project=cfg.wandb_project, name="qlora-biomistral-sanjeevani")

    print(f"Loading dataset from {cfg.dataset_path}")
    train_ds, eval_ds = load_medical_dataset(cfg.dataset_path, cfg.val_split)
    print(f"Train: {len(train_ds)} | Eval: {len(eval_ds)}")

    print(f"Loading model: {cfg.base_model}")
    model, tokenizer = load_model_and_tokenizer(cfg)
    model = apply_lora(model, cfg)

    training_args = TrainingArguments(
        output_dir=cfg.output_dir,
        num_train_epochs=cfg.num_epochs,
        per_device_train_batch_size=cfg.per_device_train_batch_size,
        gradient_accumulation_steps=cfg.gradient_accumulation_steps,
        learning_rate=cfg.learning_rate,
        lr_scheduler_type=cfg.lr_scheduler_type,
        warmup_ratio=cfg.warmup_ratio,
        weight_decay=cfg.weight_decay,
        optim=cfg.optim,
        fp16=False,
        bf16=True,
        max_grad_norm=0.3,
        save_strategy="steps",
        save_steps=cfg.save_steps,
        eval_strategy="steps",
        eval_steps=cfg.eval_steps,
        logging_steps=cfg.logging_steps,
        save_total_limit=cfg.save_total_limit,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        report_to=cfg.report_to if os.getenv("WANDB_API_KEY") else "none",
        group_by_length=True,          # speeds up training ~20% by batching similar lengths
    )

    trainer = SFTTrainer(
        model=model,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        dataset_text_field="text",
        max_seq_length=cfg.max_seq_length,
        tokenizer=tokenizer,
        args=training_args,
        packing=False,
    )

    print("Starting training...")
    trainer.train()

    print(f"Saving to {cfg.output_dir}")
    trainer.save_model(cfg.output_dir)
    tokenizer.save_pretrained(cfg.output_dir)

    print("Training complete!")
    if os.getenv("WANDB_API_KEY"):
        wandb.finish()


if __name__ == "__main__":
    cfg = TrainingConfig()
    train(cfg)
