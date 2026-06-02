from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader


DEFAULT_PDFS = [
    "/Users/woo/Downloads/MAT1002 Final 2021(1).pdf",
    "/Users/woo/Downloads/MAT1002 Final 2022.pdf",
    "/Users/woo/Downloads/MAT1002 Final 2023(1).pdf",
    "/Users/woo/Downloads/MAT1002 Final 2024(1) (1).pdf",
    "/Users/woo/Downloads/MAT1002_Final_2025.pdf",
]

DEFAULT_OUTPUT = "/Users/woo/Documents/New project/MAT1002_pdf_quick_review_report.md"
DEFAULT_JSON_OUTPUT = "/Users/woo/Documents/New project/MAT1002_pdf_question_analysis.json"


@dataclass
class Document:
    document_id: str
    document_name: str
    pages: list[dict]
    warnings: list[str] = field(default_factory=list)


@dataclass
class Question:
    document_id: str
    document_name: str
    question_id: str
    page_start: int | None
    page_end: int | None
    raw_text: str
    subparts: list[str]
    uncertain_boundary: bool = False


@dataclass
class KnowledgePoint:
    name: str
    normalized_name: str
    category: str
    formulas: list[str]
    meaning: dict[str, str]
    conceptual_meaning: str
    role_in_question: str
    original_terms: list[str]


@dataclass
class QuestionAnalysis:
    document_id: str
    document_name: str
    question_id: str
    pages: list[int]
    knowledge_points: list[KnowledgePoint]


@dataclass
class KnowledgePointSummary:
    normalized_name: str
    display_name: str
    category: str
    count: int
    formulas: list[str]
    meanings: dict[str, str]
    conceptual_meaning: str
    appears_in: list[dict]
    original_terms: list[str]


@dataclass(frozen=True)
class KnowledgeRule:
    name: str
    category: str
    formulas: tuple[str, ...]
    meaning: dict[str, str]
    conceptual_meaning: str
    role_in_question: str
    patterns: tuple[str, ...]


@dataclass
class AnalysisResult:
    documents: list[Document]
    questions: list[Question]
    analyses: list[QuestionAnalysis]
    summaries: list[KnowledgePointSummary]
    report: str
    output_path: Path
    json_output_path: Path


QUESTION_START_RE = re.compile(
    r"(?m)^\s*(?P<qid>\d{1,2})\.\s*"
    r"(?=(?:\[[^\]]+\]|\(\s*\d+\s*points?\s*\)))"
)

PAGE_MARK_RE = re.compile(r"<<<PAGE:(\d+)>>>")


RULES: list[KnowledgeRule] = [
    KnowledgeRule(
        name="Double Integrals and Fubini's Theorem",
        category="Multiple Integrals",
        formulas=("∫∫_D f(x,y) dA", "∫_a^b ∫_{g_1(x)}^{g_2(x)} f(x,y) dy dx"),
        meaning={"D": "integration region", "dA": "area element"},
        conceptual_meaning="Set up or evaluate planar accumulation by describing the region and choosing an integration order.",
        role_in_question="Describe a plane region, switch order when useful, or compute an area/integral.",
        patterns=(
            r"double integral",
            r"(?-i:\bdA\b)",
            r"area of the region",
            r"region bounded by",
            r"evaluate the following integrals",
            r"change order",
        ),
    ),
    KnowledgeRule(
        name="Triple Integrals and Volume",
        category="Multiple Integrals",
        formulas=("V = ∫∫∫_D 1 dV", "∫∫∫_D f(x,y,z) dV"),
        meaning={"D": "solid region", "dV": "volume element"},
        conceptual_meaning="Represent volume or total accumulation over a three-dimensional solid.",
        role_in_question="Set up or evaluate volume integrals over solids bounded by planes, spheres, cones, cylinders, or paraboloids.",
        patterns=(
            r"triple integral",
            r"∫∫∫",
            r"ZZZ",
            r"\bdV\b",
            r"volume of the solid",
            r"volume of the remaining solid",
            r"solid enclosed",
            r"solid that lies",
            r"first octant",
        ),
    ),
    KnowledgeRule(
        name="Cylindrical and Spherical Coordinates",
        category="Coordinate Systems",
        formulas=("x = r cos θ, y = r sin θ, dV = r dz dr dθ", "x = ρ sin φ cos θ, y = ρ sin φ sin θ, z = ρ cos φ, dV = ρ² sin φ dρ dφ dθ"),
        meaning={"r": "distance from z-axis", "ρ": "distance from origin", "θ": "azimuthal angle", "φ": "polar angle"},
        conceptual_meaning="Use symmetry to simplify regions and volume/surface integrals.",
        role_in_question="Rewrite integrals or describe solids in cylindrical or spherical coordinates.",
        patterns=(
            r"cylindrical coordinates?",
            r"spherical coordinates?",
            r"\bρ\b",
            r"\brho\b",
            r"rewrite.*(?:cylindrical|spherical).*coordinates?",
            r"triple integral.*(?:sphere|cylinder|cone|paraboloid)",
            r"volume.*(?:sphere|cylinder|cone|paraboloid|solid ball)",
        ),
    ),
    KnowledgeRule(
        name="Polar Coordinates and Polar Area",
        category="Coordinate Systems",
        formulas=("x = r cos θ, y = r sin θ", "A = 1/2 ∫ r(θ)^2 dθ"),
        meaning={"r": "distance from origin", "θ": "polar angle"},
        conceptual_meaning="Translate planar regions or curves into polar form, especially when circular or radial symmetry appears.",
        role_in_question="Sketch polar curves, describe regions, or compute enclosed area.",
        patterns=(
            r"polar coordinate",
            r"polar equation",
            r"first quadrant",
            r"inside the circle",
            r"outside the circle",
        ),
    ),
    KnowledgeRule(
        name="Change of Variables and Jacobian",
        category="Multiple Integrals",
        formulas=("∫∫_R f(x,y) dA = ∫∫_G f(x(u,v),y(u,v)) |J| du dv", "J = det(∂(x,y)/∂(u,v))"),
        meaning={"J": "Jacobian determinant", "G": "transformed region"},
        conceptual_meaning="Transform a difficult region or integrand into better coordinates while scaling area correctly.",
        role_in_question="Use a specified transformation and Jacobian to rewrite an integral.",
        patterns=(
            r"transformation",
            r"Jacobian",
            r"\bu\s*=",
            r"\bv\s*=",
            r"uv-plane",
            r"change of variables",
        ),
    ),
    KnowledgeRule(
        name="Multivariable Limits",
        category="Limits and Continuity",
        formulas=("lim_(x,y)->(a,b) f(x,y)", "path comparison"),
        meaning={"path": "approach curve used to test uniqueness of the limit"},
        conceptual_meaning="A multivariable limit exists only when all approach paths give the same value.",
        role_in_question="Test limits by direct estimates, polar coordinates, or finding two paths with different values.",
        patterns=(
            r"Determine.*limit",
            r"limit exists",
            r"lim\s*\(x,\s*y\)",
            r"lim\(x,\s*y\)",
            r"\(x,\s*y\)\s*→",
            r"\(x,\s*y\)!\(",
            r"approaching along",
        ),
    ),
    KnowledgeRule(
        name="Continuity and Differentiability in Several Variables",
        category="Limits and Continuity",
        formulas=("f is differentiable => f is continuous", "f(a+h,b+k) = f(a,b) + L(h,k) + o(√(h²+k²))"),
        meaning={"L": "linear approximation"},
        conceptual_meaning="Continuity, partial derivatives, and differentiability are distinct in several variables.",
        role_in_question="Judge continuity or differentiability, often at a piecewise-defined point.",
        patterns=(
            r"differentiable at",
            r"Determine whether .*continuous",
            r"Determine whether .*differentiable",
            r"partial derivatives?.*continuous",
            r"continuous function.*attains",
            r"continuous with respect",
            r"function continuous on",
            r"separately continuous",
        ),
    ),
    KnowledgeRule(
        name="Partial Derivatives and Clairaut's Theorem",
        category="Differentiation",
        formulas=("f_x, f_y, f_xx, f_xy, f_yx, f_yy", "f_xy = f_yx under continuity hypotheses"),
        meaning={"f_xy": "differentiate first in x then y, depending on convention/context"},
        conceptual_meaning="Compute and compare first- and second-order partial derivatives.",
        role_in_question="Find partial derivatives, second partials, or use equality of mixed partial derivatives.",
        patterns=(
            r"partial derivatives?",
            r"second-order derivatives?",
            r"second-order partial",
            r"\bfxx\b",
            r"\bfxy\b",
            r"\bfyy\b",
            r"∂2f",
            r"∂\^2f",
            r"Clairaut",
        ),
    ),
    KnowledgeRule(
        name="Directional Derivatives and Gradient",
        category="Differentiation",
        formulas=("D_u f = ∇f · u", "steepest increase direction = ∇f/||∇f||"),
        meaning={"∇f": "gradient vector", "u": "unit direction vector"},
        conceptual_meaning="The gradient gives directional rates of change and points toward steepest increase.",
        role_in_question="Compute a directional derivative or fastest increase/decrease direction.",
        patterns=(
            r"directional derivative",
            r"direction derivative",
            r"increases? the most rapidly",
            r"decrease the fastest",
            r"∇f",
            r"fastest",
        ),
    ),
    KnowledgeRule(
        name="Chain Rule for Paths and Coordinates",
        category="Differentiation",
        formulas=("d/dt f(r(t),t) = ∇f(r(t),t) · r'(t) + f_t", "∂w/∂θ = f_x x_θ + f_y y_θ + f_z z_θ"),
        meaning={"r(t)": "position curve", "θ": "coordinate parameter"},
        conceptual_meaning="Rates along curves or coordinate substitutions are obtained by composing derivatives.",
        role_in_question="Find temperature or scalar-field rate along a moving path, arc length, or coordinate substitution.",
        patterns=(
            r"rate of change",
            r"with respect to time",
            r"\bdT/dt\b",
            r"\bdF\s*/\s*ds\b",
            r"arc length",
            r"substitute spherical coordinates",
            r"@w",
            r"∂w",
        ),
    ),
    KnowledgeRule(
        name="Taylor Approximation in Several Variables",
        category="Differentiation",
        formulas=("f(a+h,b+k) ≈ f(a,b) + ∇f(a,b)·(h,k) + 1/2 [h k] H [h k]^T",),
        meaning={"H": "Hessian matrix"},
        conceptual_meaning="Approximate a multivariable function locally using derivatives up to a specified order.",
        role_in_question="Build a quadratic approximation or use Taylor's theorem in two variables.",
        patterns=(
            r"quadratic approximation",
            r"Taylor.?s theorem",
            r"Taylor.?s formula",
            r"Taylor approximation",
        ),
    ),
    KnowledgeRule(
        name="Tangent Planes and Normal Lines",
        category="Differentiation",
        formulas=("F_x(a,b,c)(x-a)+F_y(a,b,c)(y-b)+F_z(a,b,c)(z-c)=0", "z-z0 = f_x(x0,y0)(x-x0)+f_y(x0,y0)(y-y0)"),
        meaning={"∇F": "normal vector to an implicit surface"},
        conceptual_meaning="Local linearization of a surface determines its tangent plane and normal line.",
        role_in_question="Find tangent planes, normal lines, or tangent directions to level curves/surfaces.",
        patterns=(
            r"tangent plane",
            r"plane tangent",
            r"normal line",
            r"tangent line",
        ),
    ),
    KnowledgeRule(
        name="Implicit Differentiation and Level Sets",
        category="Differentiation",
        formulas=("F(x,y,z)=c", "∇F is normal to a level surface"),
        meaning={"level set": "points where a scalar function has a fixed value"},
        conceptual_meaning="Implicit equations define curves/surfaces whose geometry is controlled by gradients.",
        role_in_question="Handle implicit surfaces, contour curves, level curves, level surfaces, domains, and ranges.",
        patterns=(
            r"implicitly",
            r"implicit",
            r"level surfaces?",
            r"level curves?",
            r"contour curve",
            r"domain and the range",
            r"surface given by",
        ),
    ),
    KnowledgeRule(
        name="Critical Points and Hessian Test",
        category="Optimization",
        formulas=("∇f = 0", "D = f_xx f_yy - f_xy²"),
        meaning={"D": "2D Hessian determinant/discriminant"},
        conceptual_meaning="Classify unconstrained local extrema using first derivatives and second derivative information.",
        role_in_question="Find and classify local maxima, minima, and saddle points.",
        patterns=(
            r"critical points?",
            r"local maxim",
            r"local minim",
            r"saddle",
            r"Hessian",
            r"classify",
        ),
    ),
    KnowledgeRule(
        name="Constrained Optimization and Lagrange Multipliers",
        category="Optimization",
        formulas=("∇f = λ∇g", "∇f = λ∇g + μ∇h"),
        meaning={"λ, μ": "Lagrange multipliers for constraints"},
        conceptual_meaning="Optimize a function on curves, surfaces, or intersections defined by constraints.",
        role_in_question="Find constrained extrema or nearest points under plane/sphere/line constraints.",
        patterns=(
            r"Lagrange",
            r"constraints?",
            r"subject to",
            r"minimum distance",
            r"maximum value.*sphere",
            r"maximum and minimum.*sphere",
            r"highest and lowest",
            r"global extrema",
            r"on the sphere",
        ),
    ),
    KnowledgeRule(
        name="Extreme Value Theorem",
        category="Optimization",
        formulas=("continuous f on compact D attains absolute max and min",),
        meaning={"compact": "closed and bounded in Euclidean space"},
        conceptual_meaning="Continuity on a closed and bounded set guarantees absolute extrema.",
        role_in_question="Decide whether maxima/minima must exist on a given region.",
        patterns=(
            r"absolute maximum",
            r"absolute minimum",
            r"closed and bounded",
            r"attain",
            r"there must exist",
        ),
    ),
    KnowledgeRule(
        name="Vector Geometry in 3D",
        category="Geometry",
        formulas=("a · b = ||a||||b|| cos θ", "proj_b a = (a·b/||b||²)b", "n = a × b"),
        meaning={"a × b": "vector perpendicular to both a and b"},
        conceptual_meaning="Dot products, cross products, projections, and normal vectors describe lines, planes, and distances.",
        role_in_question="Compute angles, projections, planes, normal vectors, or closest points.",
        patterns=(
            r"parallelogram",
            r"vector projection",
            r"interior angle",
            r"plane containing",
            r"parallel to both",
            r"intersection line",
            r"minimum distance from the origin",
        ),
    ),
    KnowledgeRule(
        name="Curvature and Principal Normal",
        category="Geometry",
        formulas=("κ = ||T'(t)|| / ||r'(t)||", "N = T'/||T'||"),
        meaning={"κ": "curvature", "T": "unit tangent vector", "N": "principal unit normal"},
        conceptual_meaning="Curvature measures how fast a curve bends; the principal normal points toward bending.",
        role_in_question="Compute curvature or principal normal for a parametrized or graph curve.",
        patterns=(
            r"curvature",
            r"principal unit normal",
            r"principle unit normal",
        ),
    ),
    KnowledgeRule(
        name="Series Convergence Tests",
        category="Series",
        formulas=("comparison test", "alternating series test", "absolute vs conditional convergence"),
        meaning={"absolute convergence": "∑|a_n| converges", "conditional convergence": "∑a_n converges but ∑|a_n| diverges"},
        conceptual_meaning="Determine whether infinite sums converge and how strong the convergence is.",
        role_in_question="Apply comparison, alternating, or convergence logic to a series.",
        patterns=(
            r"series",
            r"converges?",
            r"alternating",
            r"absolute or conditional",
            r"∑∞",
            r"∞∑",
        ),
    ),
    KnowledgeRule(
        name="Power Series and Maclaurin Series",
        category="Series",
        formulas=("f(x)=∑ a_n x^n", "Maclaurin series centered at 0"),
        meaning={"a_n": "series coefficient"},
        conceptual_meaning="Represent functions locally by infinite polynomial expansions.",
        role_in_question="Find Taylor/Maclaurin terms or interval of convergence for a power series.",
        patterns=(
            r"Maclaurin",
            r"Taylor series",
            r"first .* nonzero terms",
            r"power series",
            r"interval of convergence",
            r"radius of convergence",
            r"\bn!\b",
        ),
    ),
    KnowledgeRule(
        name="Single-Variable Limits and Asymptotic Expansions",
        category="Limits and Continuity",
        formulas=("sin x ~ x", "1 - cos x ~ x²/2"),
        meaning={"~": "asymptotically equivalent near the limit point"},
        conceptual_meaning="Use standard expansions or l'Hopital-style reasoning for one-variable limits.",
        role_in_question="Evaluate single-variable limits involving trigonometric expansions.",
        patterns=(
            r"limx",
            r"x!0",
        ),
    ),
    KnowledgeRule(
        name="Line Integrals",
        category="Vector Calculus",
        formulas=("∫_C F · dr", "∫_C f ds"),
        meaning={"C": "curve/path", "dr": "tangent displacement", "ds": "arc length element"},
        conceptual_meaning="Integrate scalar or vector fields along curves.",
        role_in_question="Compute work, circulation, scalar line integrals, or compare integral magnitude to arc-length bounds.",
        patterns=(
            r"line integral",
            r"∫\s*C",
            r"\\int_C",
            r"F·dr",
            r"F·d",
            r"around and across",
            r"closed path",
            r"piecewise smooth",
        ),
    ),
    KnowledgeRule(
        name="Conservative Vector Fields and Potential Functions",
        category="Vector Calculus",
        formulas=("F = ∇φ", "∂P/∂y = ∂Q/∂x", "work = φ(B)-φ(A)"),
        meaning={"φ": "potential function", "F": "vector field"},
        conceptual_meaning="A conservative field has path-independent work and can be written as a gradient.",
        role_in_question="Check conservativeness, find a potential function, or compute work from endpoint values.",
        patterns=(
            r"conservative",
            r"potential function",
            r"gradient field",
            r"component test",
            r"work done",
            r"path independent",
        ),
    ),
    KnowledgeRule(
        name="Green's Theorem",
        category="Vector Calculus",
        formulas=("∮_C P dx + Q dy = ∬_R (Q_x - P_y) dA", "flux form: ∮_C F·n ds = ∬_R div F dA"),
        meaning={"C": "positively oriented boundary curve", "R": "enclosed region"},
        conceptual_meaning="Convert planar circulation or flux around a closed curve into a double integral over its region.",
        role_in_question="Compute circulation, outward flux, or area enclosed by a plane curve.",
        patterns=(
            r"Green",
            r"circulation",
            r"outward flux.*through C",
            r"flux.*closed path",
            r"counterclockwise",
            r"area A\(R\)",
            r"boundary of the triangle",
            r"closed semicircular",
            r"semicircle",
        ),
    ),
    KnowledgeRule(
        name="Stokes' Theorem",
        category="Vector Calculus",
        formulas=("∬_S (∇×F)·n dS = ∮_∂S F·dr",),
        meaning={"∂S": "boundary curve of the surface", "∇×F": "curl of F"},
        conceptual_meaning="Relate curl flux through a surface to circulation along its boundary.",
        role_in_question="Replace a curl surface integral by an easier boundary line integral or another surface.",
        patterns=(
            r"Stokes",
            r"curl",
            r"∇×",
            r"r⇥",
            r"curl\(F\)",
            r"flux of F through the hemisphere",
            r"surface integral",
        ),
    ),
    KnowledgeRule(
        name="Divergence and Divergence Theorem",
        category="Vector Calculus",
        formulas=("div F = ∇·F", "∬_S F·n dS = ∭_E div F dV"),
        meaning={"div F": "net source density", "S": "closed boundary surface"},
        conceptual_meaning="Divergence measures local expansion; the divergence theorem converts closed flux to a volume integral.",
        role_in_question="Compute divergence, detect expansion/contraction, or calculate outward flux through closed surfaces.",
        patterns=(
            r"\bdiv\b",
            r"r·",
            r"divergence",
            r"expanding",
            r"contracting",
            r"outward flux.*(?:surface|boundary|cube|solid|S\b)",
            r"boundary surface",
            r"boundary of .*unit outer normal",
            r"through the surface of the cube",
        ),
    ),
    KnowledgeRule(
        name="Vector Field Topology and Simply Connected Domains",
        category="Vector Calculus",
        formulas=("curl F = 0 plus simply connected domain => conservative",),
        meaning={"simply connected": "every closed loop can be continuously contracted inside the domain"},
        conceptual_meaning="Domain topology controls when component/curl tests are sufficient for conservativeness.",
        role_in_question="Judge whether a field is conservative or whether a domain is simply connected.",
        patterns=(
            r"simply connected",
            r"without the origin",
            r"passes the component test",
        ),
    ),
    KnowledgeRule(
        name="Improper Integrals",
        category="Multiple Integrals",
        formulas=("∫ near singularity", "compare in polar coordinates"),
        meaning={"singularity": "point where the integrand is unbounded or undefined"},
        conceptual_meaning="Improper integrals require checking convergence near singularities or infinite bounds.",
        role_in_question="Decide whether an integral exists as a finite real number.",
        patterns=(
            r"integral exists as a real number",
            r"1\s*/\s*x2\+y2",
            r"x2\+y2≤1",
            r"improper",
        ),
    ),
]


def clean_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = (
        text.replace("\ufb00", "ff")
        .replace("\ufb01", "fi")
        .replace("\ufb02", "fl")
        .replace("\ufb03", "ffi")
        .replace("\ufb04", "ffl")
        .replace("↵", "ff")
    )
    return text


def compact_space(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def read_documents(pdf_files: Iterable[str]) -> list[Document]:
    documents: list[Document] = []
    for idx, pdf_file in enumerate(pdf_files, start=1):
        path = Path(pdf_file)
        reader = PdfReader(str(path))
        pages: list[dict] = []
        warnings: list[str] = []
        for page_no, page in enumerate(reader.pages, start=1):
            text = clean_text(page.extract_text() or "")
            stripped = text.strip()
            pages.append({"page": page_no, "text": text})
            if len(stripped) <= 5:
                warnings.append(f"{path.name}, p.{page_no}: very little text extracted; likely blank/scanned/image-heavy.")
            elif "LEFT BLANK INTENTIONALLY" in stripped:
                warnings.append(f"{path.name}, p.{page_no}: intentionally blank page skipped during question splitting.")
        documents.append(
            Document(
                document_id=f"doc_{idx}",
                document_name=path.name,
                pages=pages,
                warnings=warnings,
            )
        )
    return documents


def page_for_index(page_positions: list[tuple[int, int]], index: int) -> int | None:
    current: int | None = None
    for pos, page in page_positions:
        if pos <= index:
            current = page
        else:
            break
    return current


def remove_page_markers_and_headers(text: str) -> str:
    text = PAGE_MARK_RE.sub("", text)
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            lines.append("")
            continue
        if re.fullmatch(r"\d{1,2}", stripped):
            continue
        if re.search(r"MA\s*T1002 Final", stripped):
            continue
        if "Final Exam Questions" in stripped or "Final Examination Questions" in stripped:
            continue
        lines.append(line)
    return compact_space("\n".join(lines))


def split_questions(document: Document) -> list[Question]:
    stream = "\n".join(
        f"\n<<<PAGE:{page['page']}>>>\n{page['text']}\n" for page in document.pages
    )
    page_positions = [(m.start(), int(m.group(1))) for m in PAGE_MARK_RE.finditer(stream)]

    start_match = re.search(r"Final (?:Exam|Examination) Questions", stream, flags=re.I)
    if start_match:
        previous_page = list(PAGE_MARK_RE.finditer(stream[: start_match.start()]))
        start_index = previous_page[-1].start() if previous_page else start_match.start()
        stream = stream[start_index:]
    else:
        first_question = re.search(r"(?m)^\s*1\.\s*\(\s*\d+\s*points?\s*\)", stream)
        if first_question:
            previous_page = list(PAGE_MARK_RE.finditer(stream[: first_question.start()]))
            start_index = previous_page[-1].start() if previous_page else first_question.start()
            stream = stream[start_index:]
        else:
            document.warnings.append(f"{document.document_name}: could not confidently locate the first question.")

    answer_match = re.search(r"(?m)^\s*Q\s*1\s+Answer\s*:", stream, flags=re.I)
    if answer_match:
        stream = stream[: answer_match.start()]
        document.warnings.append(f"{document.document_name}: answer-key pages detected and excluded from question analysis.")

    page_positions = [(m.start(), int(m.group(1))) for m in PAGE_MARK_RE.finditer(stream)]
    matches = list(QUESTION_START_RE.finditer(stream))

    if not matches:
        raw_text = remove_page_markers_and_headers(stream)
        pages = sorted({int(m.group(1)) for m in PAGE_MARK_RE.finditer(stream)})
        return [
            Question(
                document_id=document.document_id,
                document_name=document.document_name,
                question_id="Q?",
                page_start=pages[0] if pages else None,
                page_end=pages[-1] if pages else None,
                raw_text=raw_text,
                subparts=[],
                uncertain_boundary=True,
            )
        ]

    questions: list[Question] = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(stream)
        segment = stream[start:end]
        pages_inside = {int(m.group(1)) for m in PAGE_MARK_RE.finditer(segment)}
        start_page = page_for_index(page_positions, start)
        if start_page is not None:
            pages_inside.add(start_page)
        pages = sorted(pages_inside)
        raw_text = remove_page_markers_and_headers(segment)
        subparts = sorted(set(re.findall(r"\(([ivxlcdm]+|[a-z])\)", raw_text, flags=re.I)))
        questions.append(
            Question(
                document_id=document.document_id,
                document_name=document.document_name,
                question_id=f"Q{match.group('qid')}",
                page_start=pages[0] if pages else None,
                page_end=pages[-1] if pages else None,
                raw_text=raw_text,
                subparts=subparts,
            )
        )
    return questions


def normalize_knowledge_point(name: str, formulas: list[str]) -> str:
    return re.sub(r"\s+", " ", name).strip()


def matched_terms(text: str, patterns: tuple[str, ...]) -> list[str]:
    terms: list[str] = []
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I | re.S)
        if match:
            terms.append(compact_space(match.group(0))[:80])
    return terms


def analyze_question(question: Question) -> QuestionAnalysis:
    text = question.raw_text
    knowledge_points: list[KnowledgePoint] = []
    for rule in RULES:
        terms = matched_terms(text, rule.patterns)
        if not terms:
            continue
        normalized = normalize_knowledge_point(rule.name, list(rule.formulas))
        knowledge_points.append(
            KnowledgePoint(
                name=rule.name,
                normalized_name=normalized,
                category=rule.category,
                formulas=list(rule.formulas),
                meaning=dict(rule.meaning),
                conceptual_meaning=rule.conceptual_meaning,
                role_in_question=rule.role_in_question,
                original_terms=terms,
            )
        )

    unique: dict[str, KnowledgePoint] = {}
    for kp in knowledge_points:
        if kp.normalized_name not in unique:
            unique[kp.normalized_name] = kp
        else:
            existing = unique[kp.normalized_name]
            existing.original_terms = sorted(set(existing.original_terms + kp.original_terms))

    if not unique:
        unique["Unclassified / Manual Review Needed"] = KnowledgePoint(
            name="Unclassified / Manual Review Needed",
            normalized_name="Unclassified / Manual Review Needed",
            category="Manual Review",
            formulas=[],
            meaning={},
            conceptual_meaning="The heuristic analyzer did not find a strong supported topic signal.",
            role_in_question="Review the raw question manually.",
            original_terms=[],
        )

    pages = list(range(question.page_start or 0, (question.page_end or question.page_start or 0) + 1))
    if pages == [0]:
        pages = []
    return QuestionAnalysis(
        document_id=question.document_id,
        document_name=question.document_name,
        question_id=question.question_id,
        pages=pages,
        knowledge_points=sorted(unique.values(), key=lambda kp: (kp.category, kp.normalized_name)),
    )


def summarize_knowledge_points(analyses: list[QuestionAnalysis]) -> list[KnowledgePointSummary]:
    grouped: dict[str, KnowledgePointSummary] = {}
    seen_per_question: set[tuple[str, str, str]] = set()

    for analysis in analyses:
        for kp in analysis.knowledge_points:
            key = (analysis.document_id, analysis.question_id, kp.normalized_name)
            if key in seen_per_question:
                continue
            seen_per_question.add(key)
            if kp.normalized_name not in grouped:
                grouped[kp.normalized_name] = KnowledgePointSummary(
                    normalized_name=kp.normalized_name,
                    display_name=kp.name,
                    category=kp.category,
                    count=0,
                    formulas=[],
                    meanings={},
                    conceptual_meaning=kp.conceptual_meaning,
                    appears_in=[],
                    original_terms=[],
                )
            summary = grouped[kp.normalized_name]
            summary.count += 1
            summary.formulas = sorted(set(summary.formulas + kp.formulas))
            summary.meanings.update(kp.meaning)
            summary.original_terms = sorted(set(summary.original_terms + kp.original_terms))
            summary.appears_in.append(
                {
                    "document_name": analysis.document_name,
                    "question_id": analysis.question_id,
                    "pages": analysis.pages,
                }
            )

    return sorted(grouped.values(), key=lambda s: (-s.count, s.category.lower(), s.display_name.lower()))


def pages_label(pages: list[int]) -> str:
    if not pages:
        return "p.?"
    if len(pages) == 1:
        return f"p.{pages[0]}"
    return f"p.{pages[0]}-{pages[-1]}"


def year_label(document_name: str) -> str:
    match = re.search(r"20\d{2}", document_name)
    return match.group(0) if match else document_name


def compact_appears_in(items: list[dict], limit: int = 8) -> str:
    rendered = [
        f"{year_label(item['document_name'])} {item['question_id']} {pages_label(item['pages'])}"
        for item in items[:limit]
    ]
    if len(items) > limit:
        rendered.append(f"+{len(items) - limit} more")
    return "; ".join(rendered)


def md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def generate_markdown_report(
    summaries: list[KnowledgePointSummary],
    analyses: list[QuestionAnalysis],
    documents: list[Document],
    questions: list[Question],
) -> str:
    warnings = [warning for document in documents for warning in document.warnings]
    lines: list[str] = []
    lines.append("# PDF Quick Review Report")
    lines.append("")
    lines.append(f"- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"- Documents analyzed: {len(documents)}")
    lines.append(f"- Questions detected: {len(questions)}")
    lines.append(f"- Knowledge points detected: {len(summaries)}")
    lines.append("")
    lines.append("## High-Frequency Knowledge Points")
    lines.append("")
    lines.append("| Rank | Knowledge Point | Category | Count | Main Formula | Meaning | Appears In |")
    lines.append("|---|---|---|---:|---|---|---|")
    for rank, summary in enumerate(summaries, start=1):
        formula = summary.formulas[0] if summary.formulas else ""
        meaning = summary.conceptual_meaning
        lines.append(
            "| {rank} | {kp} | {cat} | {count} | {formula} | {meaning} | {appears} |".format(
                rank=rank,
                kp=md_escape(summary.display_name),
                cat=md_escape(summary.category),
                count=summary.count,
                formula=md_escape(formula),
                meaning=md_escape(meaning),
                appears=md_escape(compact_appears_in(summary.appears_in)),
            )
        )

    lines.append("")
    lines.append("## Knowledge Points by Category")
    by_category: dict[str, list[KnowledgePointSummary]] = defaultdict(list)
    for summary in summaries:
        by_category[summary.category].append(summary)

    for category in sorted(by_category):
        lines.append("")
        lines.append(f"### {category}")
        for summary in sorted(by_category[category], key=lambda s: (-s.count, s.display_name.lower())):
            lines.append("")
            lines.append(f"#### {summary.display_name}")
            lines.append("")
            lines.append(f"- Count: {summary.count}")
            if summary.formulas:
                for formula in summary.formulas:
                    lines.append(f"- Formula: `{formula}`")
            if summary.meanings:
                lines.append("- Meaning:")
                for symbol, meaning in sorted(summary.meanings.items()):
                    lines.append(f"  - `{symbol}`: {meaning}")
            lines.append("- Typical use:")
            lines.append(f"  - {summary.conceptual_meaning}")
            lines.append("- Appears in:")
            for item in summary.appears_in:
                lines.append(f"  - {item['document_name']}, {item['question_id']}, {pages_label(item['pages'])}")

    lines.append("")
    lines.append("## Question-by-Question Index")
    by_doc: dict[str, list[QuestionAnalysis]] = defaultdict(list)
    for analysis in analyses:
        by_doc[analysis.document_name].append(analysis)

    doc_order = {document.document_name: idx for idx, document in enumerate(documents)}
    for document_name in sorted(by_doc, key=lambda name: doc_order.get(name, 999)):
        for analysis in sorted(by_doc[document_name], key=lambda a: int(re.sub(r"\D", "", a.question_id) or 0)):
            lines.append("")
            lines.append(f"### {document_name} — {analysis.question_id}")
            lines.append("")
            lines.append(f"- Pages: {pages_label(analysis.pages)}")
            lines.append("- Knowledge points:")
            for kp in analysis.knowledge_points:
                lines.append(f"  - {kp.display_name if hasattr(kp, 'display_name') else kp.name}")

    lines.append("")
    lines.append("## Review Suggestions")
    lines.append("")
    top = summaries[:8]
    if top:
        lines.append(
            "1. Review the most frequent topics first: "
            + ", ".join(summary.display_name for summary in top[:5])
            + "."
        )
    else:
        lines.append("1. Review manually because no knowledge points were detected.")
    lines.append("2. For each high-frequency point, review its definition, formula, symbol meanings, and the listed exam questions.")
    lines.append("3. Practice switching among coordinate systems, integration orders, and theorem-based shortcuts because these recur across years.")
    lines.append("4. Treat rare but conceptually sharp items, such as topology or improper integrals, as high-yield true/false material.")

    lines.append("")
    lines.append("## Extraction Warnings")
    lines.append("")
    if warnings:
        for warning in warnings:
            lines.append(f"- {warning}")
    else:
        lines.append("- No extraction warnings.")

    return "\n".join(lines) + "\n"


def run_analysis(
    pdf_files: Iterable[str | Path],
    output: str | Path = DEFAULT_OUTPUT,
    json_output: str | Path = DEFAULT_JSON_OUTPUT,
) -> AnalysisResult:
    pdf_paths = [Path(pdf_file) for pdf_file in pdf_files]
    if not pdf_paths:
        raise ValueError("Select at least one PDF file to analyze.")

    missing = [str(path) for path in pdf_paths if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing PDF file(s): " + ", ".join(missing))

    documents = read_documents(str(path) for path in pdf_paths)
    questions: list[Question] = []
    for document in documents:
        questions.extend(split_questions(document))
    analyses = [analyze_question(question) for question in questions]
    summaries = summarize_knowledge_points(analyses)
    report = generate_markdown_report(summaries, analyses, documents, questions)

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")

    json_output_path = Path(json_output)
    json_output_path.parent.mkdir(parents=True, exist_ok=True)
    json_output_path.write_text(
        json.dumps(
            {
                "documents": [asdict(document) for document in documents],
                "questions": [asdict(question) for question in questions],
                "analyses": [asdict(analysis) for analysis in analyses],
                "summaries": [asdict(summary) for summary in summaries],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return AnalysisResult(
        documents=documents,
        questions=questions,
        analyses=analyses,
        summaries=summaries,
        report=report,
        output_path=output_path,
        json_output_path=json_output_path,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a MAT1002 PDF quick review report.")
    parser.add_argument("pdfs", nargs="*", default=DEFAULT_PDFS)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--json-output", default=DEFAULT_JSON_OUTPUT)
    args = parser.parse_args()

    result = run_analysis(args.pdfs, args.output, args.json_output)

    print(f"Wrote {result.output_path}")
    print(f"Wrote {result.json_output_path}")
    print(f"Documents: {len(result.documents)}")
    print(f"Questions: {len(result.questions)}")
    print(f"Knowledge points: {len(result.summaries)}")


if __name__ == "__main__":
    main()
