"""Run the frozen experiment, or audit/reproduce existing local results."""
import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import subprocess
from pathlib import Path
import numpy as np
from qiskit.quantum_info import Statevector
from src.dataset import make_dataset
from src.variational_classifier import circuit, encoded_states, probabilities
from src.training import train
from src.evaluation import accuracy, summarize, resources, save_json, load_json

ROOT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def environment():
    return {"python": platform.python_version(), "platform": platform.platform(),
            "packages": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}}


def run(output, protocol, seeds=None, steps=None, validation_only=False):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output must be empty: refusing to overwrite results")
    output.mkdir(parents=True, exist_ok=True)
    canonical = load_json(ROOT / "experiment_protocol.json")
    if protocol != canonical:
        raise ValueError("Protocol differs from frozen file")
    if not validation_only and (seeds is not None or steps is not None):
        raise ValueError("Production run cannot override seeds or budget")
    seeds = protocol["seeds"] if seeds is None else seeds
    steps = protocol["training"]["steps"] if steps is None else steps
    protocol_hash = digest(ROOT / "experiment_protocol.json")
    save_json(output / "configuration.json", {"protocol": protocol, "protocol_sha256": protocol_hash,
              "validation_only": validation_only, "actual_seeds": seeds, "actual_steps": steps})
    save_json(output / "environment.json", environment())
    rows, histories = [], {}
    for seed in seeds:
        data = make_dataset(seed)
        np.savez_compressed(output / f"dataset_seed_{seed}.npz", **data)
        initial = np.random.default_rng(seed).uniform(-0.1, 0.1, 4)
        for variant in ("RY", "ZZ"):
            trained = train(data["X_train"], data["y_train"], variant, initial, steps)
            row = {"seed": seed, "variant": variant}
            for split in ("train", "test"):
                p = probabilities(encoded_states(data[f"X_{split}"], variant), trained["theta"])
                row[f"{split}_accuracy"] = accuracy(data[f"y_{split}"], p)
            row.update(training_seconds=trained["training_seconds"], final_loss=trained["history"][-1])
            rows.append(row)
            histories[f"{seed}_{variant}"] = {"initial": initial.tolist(), **trained}
            print(f"seed={seed} variant={variant} train={row['train_accuracy']:.4f} test={row['test_accuracy']:.4f}", flush=True)
    with (output / "metrics.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = summarize(rows)
    for variant in ("RY", "ZZ"):
        group = [r for r in rows if r["variant"] == variant]
        for metric in ("train_accuracy", "training_seconds", "final_loss"):
            a = np.array([r[metric] for r in group])
            summary[variant][f"{metric}_mean"] = float(a.mean())
            summary[variant][f"{metric}_std"] = float(a.std(ddof=1)) if len(a)>1 else None
        summary[variant]["generalization_gap_mean"] = float(np.mean([r["train_accuracy"]-r["test_accuracy"] for r in group]))
    save_json(output / "summary.json", summary)
    save_json(output / "histories.json", histories)
    save_json(output / "resources.json", {v: resources(v) for v in ("RY", "ZZ")})
    for variant in ("RY", "ZZ"):
        (output / f"circuit_{variant}.txt").write_text(str(circuit([0.3,0.7],None,variant).draw(output="text")),encoding="utf-8")
    if digest(ROOT / "experiment_protocol.json") != protocol_hash:
        raise RuntimeError("Protocol changed during experiment")
    audit_results(output, expected_seeds=seeds, expected_steps=steps)
    return rows, summary


def read_rows(output):
    with (Path(output) / "metrics.csv").open(encoding="utf-8", newline="") as f:
        return [{k: int(v) if k=="seed" else v if k=="variant" else float(v) for k,v in r.items()} for r in csv.DictReader(f)]


def audit_results(output, expected_seeds=None, expected_steps=None):
    output = Path(output)
    config = load_json(output / "configuration.json")
    assert config["protocol_sha256"] == digest(ROOT / "experiment_protocol.json")
    assert config["protocol"] == load_json(ROOT / "experiment_protocol.json")
    seeds = config["actual_seeds"] if expected_seeds is None else expected_seeds
    steps = config["actual_steps"] if expected_steps is None else expected_steps
    rows = read_rows(output)
    assert len(rows) == len(seeds)*2
    assert sorted({r["seed"] for r in rows}) == sorted(seeds)
    summary, histories = load_json(output / "summary.json"), load_json(output / "histories.json")
    computed = summarize(rows)
    for k in ("seeds","delta_pp","delta_std_pp","paired_delta_pp","prediction_met"):
        assert summary[k] == computed[k]
    for v in ("RY","ZZ"):
        for k in ("test_mean","test_std"):
            assert summary[v][k] == computed[v][k]
        group=[r for r in rows if r["variant"]==v]
        for metric in ("train_accuracy","training_seconds","final_loss"):
            values=np.array([r[metric] for r in group])
            assert summary[v][f"{metric}_mean"]==float(values.mean())
            assert summary[v][f"{metric}_std"]==(float(values.std(ddof=1)) if len(values)>1 else None)
        assert load_json(output/"resources.json")[v] == resources(v)
    for seed in seeds:
        data = make_dataset(seed)
        with np.load(output / f"dataset_seed_{seed}.npz") as stored:
            for key, value in data.items():
                np.testing.assert_array_equal(stored[key], value)
        for variant in ("RY", "ZZ"):
            row = next(r for r in rows if r["seed"]==seed and r["variant"]==variant)
            h = histories[f"{seed}_{variant}"]
            np.testing.assert_array_equal(h["initial"], np.random.default_rng(seed).uniform(-0.1,0.1,4))
            assert len(h["history"]) == steps + 1
            assert np.isfinite(h["history"]).all()
            assert h["history"][-1] == row["final_loss"]
            assert h["training_seconds"] == row["training_seconds"]
            for split in ("train", "test"):
                p = probabilities(encoded_states(data[f"X_{split}"],variant),h["theta"])
                assert accuracy(data[f"y_{split}"],p) == row[f"{split}_accuracy"]
                # Independent Qiskit check of held-out cases after optimization.
                oracle=[Statevector.from_instruction(circuit(x,h["theta"],variant)).probabilities([0])[1] for x in data[f"X_{split}"][:5]]
                np.testing.assert_allclose(p[:5],oracle,atol=1e-13)
    return True


def plot_results(output, figures):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    output, figures = Path(output), Path(figures)
    figures.mkdir(parents=True, exist_ok=True)
    rows, summary, histories = read_rows(output), load_json(output/"summary.json"), load_json(output/"histories.json")
    variants=("RY","ZZ"); seeds=summary["seeds"]
    groups={v:[next(r for r in rows if r["seed"]==s and r["variant"]==v) for s in seeds] for v in variants}
    plot_data={"seeds":seeds,"test_accuracy_percent":{v:[100*r["test_accuracy"] for r in groups[v]] for v in variants},
               "train_loss":{v:[histories[f"{s}_{v}"]["history"] for s in seeds] for v in variants},
               "paired_delta_pp":summary["paired_delta_pp"],"resources":load_json(output/"resources.json"),
               "training_seconds":{v:[r["training_seconds"] for r in groups[v]] for v in variants}}
    save_json(figures/"plot_data.json",plot_data)
    fig,ax=plt.subplots(figsize=(7,4))
    for j,v in enumerate(variants):
        values=plot_data["test_accuracy_percent"][v]
        ax.scatter(np.full(len(seeds),j),values,alpha=0.65,label=f"{v}: seeds")
        ax.errorbar(j,np.mean(values),yerr=np.std(values,ddof=1),fmt="ks",capsize=8)
    ax.set(xticks=[0,1],xticklabels=variants,ylim=(0,100),ylabel="Test accuracy (%)",title="Test accuracy: seeds and mean +/- sample SD")
    fig.tight_layout(); fig.savefig(figures/"test_accuracy.png",dpi=160); plt.close(fig)
    fig,ax=plt.subplots(figsize=(7,4))
    for v in variants:
        a=np.array(plot_data["train_loss"][v]); line,=ax.plot(a.mean(axis=0),label=v)
        ax.fill_between(np.arange(a.shape[1]),a.mean(axis=0)-a.std(axis=0,ddof=1),a.mean(axis=0)+a.std(axis=0,ddof=1),alpha=0.2,color=line.get_color())
    ax.set(xlabel="Adam updates",ylabel="Train BCE",ylim=(0,None),title="Train loss: mean +/- sample SD"); ax.legend()
    fig.tight_layout(); fig.savefig(figures/"train_loss.png",dpi=160); plt.close(fig)
    fig,ax=plt.subplots(figsize=(7,4))
    ax.bar(seeds,summary["paired_delta_pp"]); ax.axhline(0,color="black"); ax.axhline(5,color="red",linestyle="--",label="Preregistered threshold: +5 pp")
    ax.set(xlabel="Seed",ylabel="ZZ - RY test accuracy (pp)",xticks=seeds,title="Paired test accuracy differences"); ax.legend()
    fig.tight_layout(); fig.savefig(figures/"paired_differences.png",dpi=160); plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(8,4))
    for ax,key,label in zip(axes,["depth","two_qubit_gates"],["Depth (gate layers)","Two-qubit gates (CX)"]):
        ax.bar(variants,[plot_data["resources"][v][key] for v in variants]); ax.set(ylabel=label,ylim=(0,None))
    fig.suptitle("Circuits in a common gate basis, optimization level 0")
    fig.tight_layout(); fig.savefig(figures/"circuit_resources.png",dpi=160); plt.close(fig)
    fig,ax=plt.subplots(figsize=(7,4))
    for j,v in enumerate(variants):
        a=plot_data["training_seconds"][v]
        ax.scatter(np.full(len(a),j),a,alpha=0.65)
        ax.errorbar(j,np.mean(a),yerr=np.std(a,ddof=1),fmt="ks",capsize=8)
    ax.set(xticks=[0,1],xticklabels=variants,ylabel="Training time (s)",ylim=(0,None),title="Serial training time: mean +/- sample SD")
    fig.tight_layout(); fig.savefig(figures/"training_time.png",dpi=160); plt.close(fig)
    save_json(figures/"manifest.json",{p.name:digest(p) for p in sorted(figures.glob("*.png"))})
    audit_figures(output,figures)


def audit_figures(output,figures):
    import matplotlib.image as mpimg
    figures=Path(figures); d=load_json(figures/"plot_data.json")
    rows=read_rows(output); summary=load_json(Path(output)/"summary.json"); histories=load_json(Path(output)/"histories.json")
    assert d["paired_delta_pp"]==summary["paired_delta_pp"]
    assert d["resources"]==load_json(Path(output)/"resources.json")
    for v in ("RY","ZZ"):
        group=[next(r for r in rows if r["seed"]==s and r["variant"]==v) for s in d["seeds"]]
        assert d["test_accuracy_percent"][v]==[100*r["test_accuracy"] for r in group]
        assert d["training_seconds"][v]==[r["training_seconds"] for r in group]
        assert d["train_loss"][v]==[histories[f"{s}_{v}"]["history"] for s in d["seeds"]]
    manifest=load_json(figures/"manifest.json")
    assert len(manifest)==5
    for name,sha in manifest.items():
        assert digest(figures/name)==sha
        pixels=mpimg.imread(figures/name)
        assert pixels.shape[0]>=400 and pixels.shape[1]>=800 and np.isfinite(pixels).all()
    return True


def reproduce(output, destination):
    config=load_json(Path(output)/"configuration.json")
    run(destination,config["protocol"])
    a,b=read_rows(output),read_rows(destination)
    for ra,rb in zip(a,b):
        for key in ra:
            if key!="training_seconds": assert ra[key]==rb[key], (key,ra,rb)
    ha,hb=load_json(Path(output)/"histories.json"),load_json(Path(destination)/"histories.json")
    for key in ha:
        for field in ("initial","theta","history"):
            assert ha[key][field]==hb[key][field], (key,field)
    save_json(Path(output)/"reproduction.json",{"passed":True,"models":len(a),"exact_equal":["initial","theta","history","train_accuracy","test_accuracy","final_loss"],"excluded":"training_seconds: wall clock is not deterministic"})


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=ROOT/"results")
    parser.add_argument("--audit",action="store_true")
    parser.add_argument("--reproduce",type=Path)
    args=parser.parse_args()
    if args.audit:
        audit_results(args.output); audit_figures(args.output,ROOT/"figures")
        print("AUDIT PASS")
    elif args.reproduce:
        reproduce(args.output,args.reproduce); print("REPRODUCTION PASS")
    else:
        run(args.output,load_json(ROOT/"experiment_protocol.json"))
        plot_results(args.output,ROOT/"figures")
        print("EXPERIMENT AND FIGURE AUDIT PASS")


if __name__=="__main__":
    main()
