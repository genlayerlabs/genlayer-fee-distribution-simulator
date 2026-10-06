"""Independent ownership ledger for observed consensus fee costs (N-B02).

Round FeeEvents establish earned time-unit work. This ledger assigns its fee
cost to immutable admissions and ordinary FIFO lots. Bond principal is outside
the fee ledger; execution costs enter only when explicitly supplied.
"""

from collections import defaultdict
from copy import deepcopy


COMPONENTS = ("taxableWork", "appellantProfit", "executionBacking", "overlay")


def _money(value, name):
    if isinstance(value, str) and value.isdecimal():
        value = int(value)
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def settle_attribution(case):
    """Allocate raw costs and one authoritative actual overlay route.

    A typed component is capped by its reservation; excess uses ordinary
    primary funding. The actual routed developer plus DAO overlay is split
    across typed admissions by cumulative taxable work, with all ordinary
    residual consumed FIFO from the separate ordinary overlay column.
    """
    ordinary = deepcopy(case.get("ordinaryFunding", []))
    rescue = deepcopy(case.get("rescueFunding", []))
    admissions = deepcopy(case.get("admissions", []))
    charges = deepcopy(case.get("charges", []))
    bps = _money(case.get("overlayBps", 0), "overlayBps")
    if bps >= 10_000:
        raise ValueError("overlayBps must be less than 10000")
    routes = case.get("actualOverlayRouted", {"developer": 0, "dao": 0})
    actual_overlay = _money(routes["developer"], "developer route") + _money(routes["dao"], "DAO route")

    funding = {}
    ordinary_order = []
    for lot in [*ordinary, *rescue]:
        key = lot["id"]
        if key in funding:
            raise ValueError(f"duplicate funding ID {key}")
        reserve = {component: _money(lot["reserve"][component], component)
                   for component in ("primary", "overlay")}
        funding[key] = {"payer": lot["payer"], "kind": "ordinary",
                        "deposited": reserve, "consumed": dict.fromkeys(reserve, 0)}
        ordinary_order.append(key)

    for admission in admissions:
        key = admission["id"]
        if key in funding:
            raise ValueError(f"duplicate funding ID {key}")
        kind = admission["quotaKind"]
        if kind not in ("inQuota", "beyondQuota"):
            raise ValueError("unknown quota kind")
        generation = _money(admission["generation"], "generation")
        book_round = _money(admission["bookRound"], "bookRound")
        if book_round % 2 != 1:
            raise ValueError("appeal bookRound must be odd")
        reserve = {component: _money(admission["reserve"][component], component)
                   for component in COMPONENTS}
        if kind == "inQuota" and reserve["appellantProfit"]:
            raise ValueError("in-quota admission cannot reserve appellant profit")
        funding[key] = {
            "payer": admission["payer"], "kind": kind,
            "generation": generation, "bookRound": book_round,
            "prepaidScheduledBase": _money(admission.get("prepaidScheduledBase", 0), "prepaidScheduledBase"),
            "replacementSeen": 0, "result": admission.get("result", "unknown"),
            "bondPrincipal": _money(admission.get("bondPrincipal", 0), "bondPrincipal"),
            "deposited": reserve, "consumed": dict.fromkeys(reserve, 0),
        }

    def available(entry, component):
        return entry["deposited"][component] - entry["consumed"][component]

    def ordinary_debit(component, amount):
        remaining = amount
        for key in ordinary_order:
            take = min(remaining, available(funding[key], component))
            funding[key]["consumed"][component] += take
            remaining -= take
            if not remaining:
                break
        if remaining:
            raise ValueError(f"overall {component} funding exhausted")

    taxable_chunks = []

    def pay_primary(source, component, amount):
        if source == "ordinary":
            ordinary_debit("primary", amount)
            return [("ordinary", amount)] if amount else []
        entry = funding[source]
        take = min(amount, available(entry, component))
        entry["consumed"][component] += take
        paid = [(source, take)] if take else []
        if amount > take:
            ordinary_debit("primary", amount - take)
            paid.append(("ordinary", amount - take))
        return paid

    for event in charges:
        amount = _money(event["amount"], "charge amount")
        source = event["sourceFundingId"]
        component = event["kind"]
        if component not in COMPONENTS[:-1]:
            raise ValueError(f"unknown primary charge kind {component}")
        if source != "ordinary":
            if source not in funding or funding[source]["kind"] == "ordinary":
                raise ValueError(f"unknown appeal funding ID {source}")
            entry = funding[source]
            if event["generation"] != entry["generation"] or event["bookRound"] != entry["bookRound"]:
                raise ValueError("charge generation/bookRound differs from immutable admission")
            if component == "appellantProfit" and (entry["kind"] != "beyondQuota" or entry["result"] != "successful"):
                raise ValueError("appellant profit requires successful beyond-quota appeal")
            if component == "taxableWork":
                work_kind = event["workKind"]
                if work_kind not in ("jury", "replacement"):
                    raise ValueError("appeal work must be jury or replacement")
                if entry["kind"] == "inQuota":
                    if work_kind != "replacement":
                        raise ValueError("in-quota jury work belongs to ordinary funding")
                    old = entry["replacementSeen"]
                    entry["replacementSeen"] += amount
                    base = entry["prepaidScheduledBase"]
                    prepaid = min(entry["replacementSeen"], base) - min(old, base)
                    ordinary_debit("primary", prepaid)
                    if prepaid:
                        taxable_chunks.append(("ordinary", prepaid))
                    amount -= prepaid
        paid = pay_primary(source, component, amount)
        if component == "taxableWork":
            taxable_chunks.extend(paid)

    total_taxable = sum(amount for _, amount in taxable_chunks)
    gross_ceiling = total_taxable * bps // (10_000 - bps)
    if actual_overlay > gross_ceiling:
        raise ValueError("actual overlay exceeds taxable-work gross-up")
    if actual_overlay and not total_taxable:
        raise ValueError("overlay routed without taxable work")

    # Aggregate before rounding: splitting one duty into several FeeEvents or
    # interleaving ordinary work cannot change an admission's ownership.
    # Admission order is immutable; ordinary receives the global residual.
    taxable_by_source = defaultdict(int)
    for source, work in taxable_chunks:
        taxable_by_source[source] += work
    cumulative = 0
    allocated_typed = 0
    ordinary_overlay = 0
    for admission in admissions:
        source = admission["id"]
        cumulative += taxable_by_source[source]
        target = cumulative * actual_overlay // total_taxable if total_taxable else 0
        due = target - allocated_typed
        allocated_typed = target
        entry = funding[source]
        take = min(due, available(entry, "overlay"))
        entry["consumed"]["overlay"] += take
        ordinary_overlay += due - take
    ordinary_overlay += actual_overlay - allocated_typed
    ordinary_capacity = sum(available(funding[key], "overlay") for key in ordinary_order)
    if ordinary_overlay > ordinary_capacity:
        # Cumulative floors can leave one wei per working admission assigned
        # to an already-full ordinary column. Only that admission's rounded-up
        # proportional duty, capped by its own overlay reserve, may absorb it.
        deficit = ordinary_overlay - ordinary_capacity
        for admission in admissions:
            if not deficit:
                break
            source = admission["id"]
            work = taxable_by_source[source]
            if not work:
                continue
            entry = funding[source]
            rounded_share = (actual_overlay * work + total_taxable - 1) // total_taxable
            ceiling = min(rounded_share, entry["deposited"]["overlay"])
            extra = min(deficit, max(0, ceiling - entry["consumed"]["overlay"]))
            entry["consumed"]["overlay"] += extra
            ordinary_overlay -= extra
            deficit -= extra
    ordinary_debit("overlay", ordinary_overlay)

    by_payer = defaultdict(lambda: {"deposited": defaultdict(int), "consumed": defaultdict(int), "refunded": defaultdict(int)})
    by_funding = []
    for key, entry in funding.items():
        refunded = {component: value - entry["consumed"][component]
                    for component, value in entry["deposited"].items()}
        for component, value in entry["deposited"].items():
            payer = by_payer[entry["payer"]]
            payer["deposited"][component] += value
            payer["consumed"][component] += entry["consumed"][component]
            payer["refunded"][component] += refunded[component]
        by_funding.append({"id": key, "payer": entry["payer"],
                           "consumed": dict(entry["consumed"]), "refunded": refunded})

    columns = ("primary", *COMPONENTS)
    output_payers = []
    for payer, values in sorted(by_payer.items()):
        row = {"payer": payer}
        for name in ("deposited", "consumed", "refunded"):
            row[name] = {component: values[name].get(component, 0) for component in columns}
        output_payers.append(row)
    result = {
        "byPayer": output_payers, "byFunding": by_funding,
        "totalDeposited": sum(sum(row["deposited"].values()) for row in output_payers),
        "totalConsumed": sum(sum(row["consumed"].values()) for row in output_payers),
        "totalRefunded": sum(sum(row["refunded"].values()) for row in output_payers),
        "overlayRouted": sum(entry["consumed"]["overlay"] for entry in funding.values()),
        "taxableWork": total_taxable,
    }
    if result["overlayRouted"] != actual_overlay:
        raise AssertionError("allocated overlay differs from actual global route")
    return result
