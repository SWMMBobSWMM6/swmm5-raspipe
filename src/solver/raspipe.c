//-----------------------------------------------------------------------------
//   raspipe.c
//
//   Project:  SWMM5 RASPIPE, a fork of EPA SWMM 5.2.4
//   Version:  1.2
//   AI use:   Code written by Claude, Anthropic's AI model, in November 2026, at
//             the direction of R. Dickinson, who is responsible for it. No person
//             has reviewed it yet. See README.md.
//
//   Semi-implicit finite volume pipe network solver, an alternative to the
//   explicit Picard solution in dynwave.c / dwflow.c.
//
//   This is an independent implementation built from what the U.S. Army Corps
//   of Engineers Hydrologic Engineering Center has published about HEC-RAS pipe
//   networks, plus the Casulli papers that documentation cites. HEC-RAS source
//   is not public and none of it is used here.
//
//   Published by HEC (Hydraulic Reference Manual 7.0, Modeling Pipe Networks
//   and Numerical Methods for Pipe Flow; User's Manual 6.6, Pipe Networks):
//     - conduits are meshed into cells; sub-grid property tables for cells & faces
//     - junction cells borrow portions of the connected conduits
//     - diffusion wave or full shallow water equations on a 1D finite volume mesh
//     - the pressure term is semi-implicit, so pressure waves set no time step
//     - no Preissmann slot: volume tables split into positive and negative parts
//       and an extra iteration loop (Casulli & Stelling 2013)
//     - water surface above a ceiling = ceiling elevation + P/gamma
//     - gates and weirs enter by changing the friction of a face
//     - flow capped by conduit capacity and by critical velocity at low flow
//     - advection: explicit Eulerian-Lagrangian backtracking, with the advective
//       speed switched by local flow, energy head in strong contractions and
//       momentum elsewhere (Stelling & Duinmeijer 2003); implicit friction;
//       outer and inner nested iterations; the split formulas for the tables
//
//   Filled in here, because HEC does not give them: what counts as a strong
//   contraction (ACONTRACT below), the centered area in the advective speed, how
//   momentum crosses a junction, the face area upwinding, the Newton
//   linearization of friction and of the face areas, trying plain Newton before
//   the nested loop, the symmetric fallback, the sparse L D U solve, table
//   spacing, tolerances and defaults, the opening of dry faces, trimming of
//   demand that can't be reached, and the formula for the residence time
//   Courant number (HEC names it and describes it in words only).
//
//   Equations solved at each time step, for cell i and face j:
//
//      V_i(eta_i) + dt theta Sum_j (+/-) Q_j(eta) = b_i
//
//      u_j (I + dt c_j |u_j|) = F_j - g dt/dx [theta d_eta(n+1) + (1-theta) d_eta(n)]
//      Q_j = A_j(eta_upstream) u_j
//
//   Q_j is linearized by Newton, including the change of wetted area with the
//   upstream level, which makes the matrix an unsymmetric M-matrix:
//
//      Q_j = Q0_j + a_j eta_L - b_j eta_R       a_j, b_j >= 0
//
//   V_i is a monotone, piecewise linear volume table that stops rising at the
//   crown of a closed cell, which is why no slot is needed. It is written as
//   V1 - V2, both convex (the Jordan decomposition of dV/d(eta)) and solved by
//   the nested Newton iteration of Casulli & Zanolli (2012).
//-----------------------------------------------------------------------------
#define _CRT_SECURE_NO_DEPRECATE

#include <stdlib.h>
#include <string.h>
#include <math.h>
#include "headers.h"

#ifndef RASPIPE_BUILD
#define RASPIPE_BUILD "unstamped"
#endif

//-----------------------------------------------------------------------------
//  Constants
//-----------------------------------------------------------------------------
#define NGEO      64                   // intervals in a section table
#define MAXOUTER  80                   // nested Newton outer iterations
#define MAXTRIALS 8                    // the solve is conservative at any trial
#define MAXINNER  24                   // nested Newton inner iterations

static const double TFLOOD   = 1.0e7;  // virtual area above a flooded node (ft2)
static const double VTOL     = 1.0e-8; // volume residual tolerance (ft3)
static const double DRYDEPTH = 1.0e-6; // depth treated as dry (ft)
static const double SLOPE0   = 1.0e-6; // water surface slope below which diffusion
                                       // wave friction turns linear (ft/ft)
static const double RMIN     = 1.0e-3; // smallest hyd. radius in friction (ft)
static const double QTOL     = 0.01;   // flow convergence, fraction of flow
static const double ETAFLOOR = 500.0;  // how far a dry cell's level may sink (ft)
static const double ETACEIL  = 2.0e5;  // backstop on a sealed run's level (ft)
static const double SEALAREA = 1.0e-6; // ft2, see nestedNewton
static const double ACONTRACT = 1.5;   // upwind/face area ratio taken as a strong
                                       // contraction; HEC gives no number

//-----------------------------------------------------------------------------
//  Data Structures
//-----------------------------------------------------------------------------
typedef struct                         // one conduit & its section tables
{
    int    link;                       // SWMM link index
    int    k;                          // SWMM conduit index
    int    f0, nf;                     // first face, number of faces
    int    c0, nc;                     // first interior cell, number of them
    double L, delta, z1, z2, barrels, qScale;
    double yFull, aFull, rFull, dy;
    double evapSum, seepSum;           // conduit losses over the routing step
    double vp1, vp2, vp1Old, vp2Old;   // volume in the pieces the end cells borrow
    double qUp, qDn;                   // flow at each end of the whole conduit
    double a[NGEO+1], g[NGEO+1], r[NGEO+1], w[NGEO+1];
} TPipe;

typedef struct                         // volume table with Jordan split
{
    int     n;                         // number of break points
    double *e, *v, *v1, *v2;           // values at break points
    double *t1, *t2;                   // slopes on [k,k+1); [n-1] is the tail
    double  ePk;                       // where dV/d(eta) first turns down
} TTab;

typedef struct                         // borrowed piece of a conduit
{
    int    pipe, cell, next;
    double z0, z1, len;
} TPiece;

typedef struct                         // computational cell
{
    TTab  *tab;
    double shift;                      // table elevation = eta - shift
    int    node;                       // SWMM node, or -1 for interior cell
    int    pipe;                       // owning pipe for interior cell
    int    unk;                        // position in matrix, or -1 if head fixed
    int    hint;                       // last table interval
    int    canPond;
    double eta, etaLin, etaOld, vOld, zMin, etaTop, src;
} TCell;

typedef struct                         // computational face
{
    int    kind;                       // 0 conduit, 1 regulator, 2 pump/dummy
    int    link, pipe, idx;
    int    L, R;                       // cells; +Q runs from L to R
    int    edge;                       // matrix entry, or -1
    int    pcL, pcR;                   // borrowed piece of a node cell, or -1
    double z, dx, K;                   // crest, length, local loss coefficient
    double Q, Qold, A, u, uOld, deOld; // flow (all barrels), area (1 barrel)
    double I, F;                       // inertial coefficient and explicit part
    double Am;                         // area at the face, mean of the two sides
    int    thru;                       // end face across a two-conduit junction, or -1
    double thruSg;                     // +1 same sense of positive flow, -1 opposite
    double a, b, Q0;                   // Q = Q0 + a etaL - b etaR
    double Qsum, Qbar;                 // flow volume over the routing step, mean flow
    int    dir;                        // 0 two-way, +1 L to R only, -1 R to L only
    int    bc;                         // outfall: 1 free, 2 normal, 0 stage or none
    int    crest;                      // conduit end that sits on an offset or outfall
    double Qs, Cn;                     // flow and conveyance at the linearization
} TFace;

//-----------------------------------------------------------------------------
//  Shared variables
//-----------------------------------------------------------------------------
static int     Nc, Nf, Np, Npc, Nun;
static TCell  *Cell;
static TFace  *Face;
static TPipe  *Pipe;
static TPiece *Piece;
static TTab   *Tabs;
static int     Ntabs, Npieces;
static int    *PieceHead;
static char   *NeedVol;

static double *Rhs, *Res, *Diag, *X, *V2k, *P2k, *Etak, *Etap, *EtaPrev, *QPrev;
static char   *NodeConv;

static int     Ne;                     // sparse LDL^T of the cell system
static int    *Perm, *Pinv, *Ap, *Ai, *Lp, *Li, *Lnz, *Par, *Flag, *Pat, *EdgePos;
static double *Axu, *Axl, *Lx, *Ux, *D, *Y, *Z;

static double  StatOuter, StatInner, StatFact, StatSteps, StatTrials, StatNested;
static double  StatFallback;
static int     StatFail;
static int    *PipeOfLink = NULL;
static int     StatUnsolved;
static double  StatSub;
static double  StatCr, StatDtMin, StatDtMax, StatTime; // Courant & pipe step reached
static int     NCapped;                // conduits held at the cell limit
static double  DeltaMin, DeltaMed, DeltaMax; // cell length achieved
static double *FloodV = NULL;          // flood volume over the routing step
static double *OutQ = NULL;            // work space for the Courant check
static double  WarmScale = -1.0;       // inflow fraction during a warm up
static int     WarmDone;
static int     NSub;
static const double MINSUBSTEP = 0.1;  // floor when MINIMUM_STEP is zero (sec)
static const double MAXMOVINGSTEP = 15.0; // longest pipe step with water moving (sec)
static const double QUIETFLOW = 1.0e-4;   // floor on what counts as nothing (cfs)
static double  QuietQ;                     // lateral flow that counts as nothing
static const double OPENDEPTH = 0.001;    // water it takes to open a dry face (ft)
static double  MaxRes;
static double  VolIn, VolOut, VolFlood, VolStart;     // solver's own ledger (ft3)

//-----------------------------------------------------------------------------
//  Section tables
//-----------------------------------------------------------------------------
static void geoBuild(TPipe *p, TXsect *x)
{
    int i;
    double y;
    p->yFull = x->yFull;
    p->aFull = x->aFull;
    p->rFull = x->rFull;
    p->dy    = x->yFull / NGEO;
    for (i = 0; i <= NGEO; i++)
    {
        y = i * p->dy;
        p->a[i] = (i == NGEO) ? x->aFull : xsect_getAofY(x, y);
        p->r[i] = (i == 0) ? 0.0 : (i == NGEO ? x->rFull : xsect_getRofY(x, y));
        p->w[i] = xsect_getWofY(x, y);
        if (i > 0 && p->a[i] < p->a[i-1]) p->a[i] = p->a[i-1];
    }
    p->g[0] = 0.0;
    for (i = 1; i <= NGEO; i++)
        p->g[i] = p->g[i-1] + 0.5 * (p->a[i-1] + p->a[i]) * p->dy;
}

static double geoLook(TPipe *p, double *t, double y)
{
    double s = y / p->dy;
    int    i = (int)s;
    if (i >= NGEO) return t[NGEO];
    return t[i] + (s - i) * (t[i+1] - t[i]);
}

static double geoA(TPipe *p, double y)
{
    if (y <= 0.0) return 0.0;
    if (y >= p->yFull) return p->aFull;
    return geoLook(p, p->a, y);
}

static double geoR(TPipe *p, double y)
{
    if (y <= 0.0) return 0.0;
    if (y >= p->yFull) return p->rFull;
    return geoLook(p, p->r, y);
}

static double geoW(TPipe *p, double y)
{
    if (y <= 0.0) return 0.0;
    if (y >= p->yFull) return p->w[NGEO];
    return geoLook(p, p->w, y);
}

static double geoG(TPipe *p, double y)                 // integral of A dy
{
    int    i;
    double s;
    if (y <= 0.0) return 0.0;
    if (y >= p->yFull) return p->g[NGEO] + p->aFull * (y - p->yFull);
    i = (int)(y / p->dy);
    if (i >= NGEO) i = NGEO - 1;
    s = y - i * p->dy;
    return p->g[i] + s * (p->a[i] + 0.5 * s * (p->a[i+1] - p->a[i]) / p->dy);
}

static double geoYofA(TPipe *p, double a)              // inverse of geoA
{
    int lo = 0, hi = NGEO, m;
    if (a <= 0.0) return 0.0;
    if (a >= p->aFull) return p->yFull;
    while (hi - lo > 1)
    {
        m = (lo + hi) / 2;
        if (p->a[m] <= a) lo = m; else hi = m;
    }
    if (p->a[hi] <= p->a[lo]) return lo * p->dy;
    return (lo + (a - p->a[lo]) / (p->a[hi] - p->a[lo])) * p->dy;
}

static double geoDA(TPipe *p, double y)                // dA/dy
{
    int i = (int)(y / p->dy);
    if (i >= NGEO) i = NGEO - 1;
    return (p->a[i+1] - p->a[i]) / p->dy;
}

static double geoDK(TPipe *p, double y)                // d ln(A R^2/3) / dy
{
    int    i = (int)(y / p->dy);
    double k0, k1;
    if (i >= NGEO) i = NGEO - 1;
    k0 = p->a[i] * pow(p->r[i], 0.6666666667);
    k1 = p->a[i+1] * pow(p->r[i+1], 0.6666666667);
    if (i == 0) return 1.8 / MAX(y, 0.05 * p->dy);     // K ~ y^1.8 near the invert
    return (k1 - k0) / p->dy / (0.5 * (k0 + k1));
}

static double pieceV(TPipe *p, double eta, double z0, double z1, double len)
{
    double zlo = MIN(z0, z1), zhi = MAX(z0, z1);
    if (zhi - zlo < 1.0e-9) return geoA(p, eta - zlo) * len;
    return (geoG(p, eta - zlo) - geoG(p, eta - zhi)) * len / (zhi - zlo);
}

//-----------------------------------------------------------------------------
//  Volume tables
//-----------------------------------------------------------------------------
static void tabAlloc(TTab *t, int n)
{
    t->n  = n;
    t->e  = (double *)calloc(n, sizeof(double));
    t->v  = (double *)calloc(n, sizeof(double));
    t->v1 = (double *)calloc(n, sizeof(double));
    t->v2 = (double *)calloc(n, sizeof(double));
    t->t1 = (double *)calloc(n, sizeof(double));
    t->t2 = (double *)calloc(n, sizeof(double));
}

static void tabFree(TTab *t)
{
    FREE(t->e); FREE(t->v); FREE(t->v1); FREE(t->v2); FREE(t->t1); FREE(t->t2);
}

static void tabSplit(TTab *t, double tail)     // Jordan split of dV/d(eta)
{
    int    k, n = t->n;
    double slope, d, prev = 0.0, up = 0.0, dn = 0.0;
    for (k = 1; k < n; k++) if (t->v[k] < t->v[k-1]) t->v[k] = t->v[k-1];
    for (k = 0; k < n; k++)
    {
        slope = (k < n - 1) ? (t->v[k+1] - t->v[k]) / (t->e[k+1] - t->e[k]) : tail;
        d = slope - prev;
        if (d > 0.0) up += d; else dn -= d;
        t->t1[k] = up;
        t->t2[k] = dn;
        prev = slope;
    }
    t->ePk = 1.0e30;
    for (k = 0; k < n; k++) if (t->t2[k] > 0.0) { t->ePk = t->e[k]; break; }
    t->v1[0] = t->v[0];
    t->v2[0] = 0.0;
    for (k = 0; k < n - 1; k++)
    {
        d = t->e[k+1] - t->e[k];
        t->v1[k+1] = t->v1[k] + t->t1[k] * d;
        t->v2[k+1] = t->v2[k] + t->t2[k] * d;
    }
}

static int tabFind(TTab *t, double x, int *hint)
{
    int k = *hint, lo, hi, m, n = t->n;
    if (x < t->e[0]) return -1;
    if (k >= 0 && k < n && x >= t->e[k] && (k == n - 1 || x < t->e[k+1])) return k;
    if (k >= 0 && k + 1 < n && x >= t->e[k+1] && (k + 1 == n - 1 || x < t->e[k+2]))
        return *hint = k + 1;
    if (k > 0 && k < n && x < t->e[k] && x >= t->e[k-1]) return *hint = k - 1;
    lo = 0; hi = n - 1;
    while (lo < hi)
    {
        m = (lo + hi + 1) / 2;
        if (x >= t->e[m]) lo = m; else hi = m - 1;
    }
    return *hint = lo;
}

static double cellV(TCell *c, double eta)
{
    double x = eta - c->shift;
    int    k = tabFind(c->tab, x, &c->hint);
    TTab  *t = c->tab;
    if (k < 0) return 0.0;
    x -= t->e[k];
    return t->v1[k] - t->v2[k] + (t->t1[k] - t->t2[k]) * x;
}

//-----------------------------------------------------------------------------
//  Sparse L D U on a symmetric pattern: minimum degree order, symbolic and
//  numeric factors. The matrix is an M-matrix, so no pivoting is needed.
//-----------------------------------------------------------------------------
typedef struct { int a, b; } TEdge;

static int edgeCmp(const void *x, const void *y)
{
    const TEdge *p = (const TEdge *)x, *q = (const TEdge *)y;
    if (p->a != q->a) return p->a < q->a ? -1 : 1;
    if (p->b != q->b) return p->b < q->b ? -1 : 1;
    return 0;
}

static void mdOrder(int n, int ne, TEdge *e, int *order)
{
    int  **adj, *deg, *cap, *head, *nxt, *prv, *mark, *gone;
    int    i, j, k, v, u, w, d, dmin, pos;

    adj  = (int **)calloc(n + 1, sizeof(int *));
    deg  = (int *)calloc(n + 1, sizeof(int));
    cap  = (int *)calloc(n + 1, sizeof(int));
    head = (int *)malloc((n + 2) * sizeof(int));
    nxt  = (int *)malloc((n + 1) * sizeof(int));
    prv  = (int *)malloc((n + 1) * sizeof(int));
    mark = (int *)malloc((n + 1) * sizeof(int));
    gone = (int *)calloc(n + 1, sizeof(int));

    for (i = 0; i < ne; i++) { deg[e[i].a]++; deg[e[i].b]++; }
    for (i = 0; i < n; i++)
    {
        cap[i] = deg[i] + 4;
        adj[i] = (int *)malloc(cap[i] * sizeof(int));
        deg[i] = 0;
        mark[i] = -1;
    }
    for (i = 0; i < ne; i++)
    {
        adj[e[i].a][deg[e[i].a]++] = e[i].b;
        adj[e[i].b][deg[e[i].b]++] = e[i].a;
    }
    for (i = 0; i <= n; i++) head[i] = -1;
    for (i = 0; i < n; i++)
    {
        nxt[i] = head[deg[i]];
        prv[i] = -1;
        if (nxt[i] >= 0) prv[nxt[i]] = i;
        head[deg[i]] = i;
    }

    dmin = 0;
    for (pos = 0; pos < n; pos++)
    {
        while (dmin < n && head[dmin] < 0) dmin++;
        v = head[dmin];
        head[dmin] = nxt[v];
        if (nxt[v] >= 0) prv[nxt[v]] = -1;
        order[pos] = v;
        gone[v] = 1;

        for (i = 0; i < deg[v]; i++)
        {
            u = adj[v][i];
            if (prv[u] >= 0) nxt[prv[u]] = nxt[u]; else head[deg[u]] = nxt[u];
            if (nxt[u] >= 0) prv[nxt[u]] = prv[u];
        }
        for (i = 0; i < deg[v]; i++)
        {
            u = adj[v][i];
            for (j = k = 0; j < deg[u]; j++)
                if (adj[u][j] != v) { adj[u][k++] = adj[u][j]; mark[adj[u][k-1]] = u; }
            mark[u] = u;
            deg[u] = k;
            for (j = 0; j < deg[v]; j++)
            {
                w = adj[v][j];
                if (mark[w] == u) continue;
                if (deg[u] == cap[u])
                {
                    cap[u] = 2 * cap[u] + 4;
                    adj[u] = (int *)realloc(adj[u], cap[u] * sizeof(int));
                }
                adj[u][deg[u]++] = w;
                mark[w] = u;
            }
        }
        for (i = 0; i < deg[v]; i++)
        {
            u = adj[v][i];
            d = deg[u];
            nxt[u] = head[d];
            prv[u] = -1;
            if (nxt[u] >= 0) prv[nxt[u]] = u;
            head[d] = u;
            if (d < dmin) dmin = d;
        }
    }
    for (i = 0; i < n; i++) free(adj[i]);
    free(adj); free(deg); free(cap); free(head); free(nxt); free(prv); free(mark);
    free(gone);
}

static void ldlSymbolic(int n, int ne, TEdge *e)
{
    int  i, k, p, lnzTotal;
    int *order = (int *)malloc((n + 1) * sizeof(int));
    int *cnt;

    mdOrder(n, ne, e, order);
    Perm = (int *)malloc((n + 1) * sizeof(int));
    Pinv = (int *)malloc((n + 1) * sizeof(int));
    for (i = 0; i < n; i++) { Perm[i] = order[i]; Pinv[order[i]] = i; }
    free(order);

    Ap = (int *)calloc(n + 2, sizeof(int));
    Ai = (int *)malloc((ne + 1) * sizeof(int));
    Axu = (double *)calloc(ne + 1, sizeof(double));
    Axl = (double *)calloc(ne + 1, sizeof(double));
    EdgePos = (int *)malloc((ne + 1) * sizeof(int));
    for (i = 0; i < ne; i++) Ap[MAX(Pinv[e[i].a], Pinv[e[i].b]) + 1]++;
    for (k = 0; k < n; k++) Ap[k+1] += Ap[k];
    cnt = (int *)calloc(n + 1, sizeof(int));
    for (i = 0; i < ne; i++)
    {
        int a = Pinv[e[i].a], b = Pinv[e[i].b];
        k = MAX(a, b);
        p = Ap[k] + cnt[k]++;
        Ai[p] = MIN(a, b);
        EdgePos[i] = p;
    }
    free(cnt);

    Par  = (int *)malloc((n + 1) * sizeof(int));
    Flag = (int *)malloc((n + 1) * sizeof(int));
    Lnz  = (int *)calloc(n + 1, sizeof(int));
    Pat  = (int *)malloc((n + 1) * sizeof(int));
    Lp   = (int *)calloc(n + 2, sizeof(int));
    D    = (double *)calloc(n + 1, sizeof(double));
    Y    = (double *)calloc(n + 1, sizeof(double));
    Z    = (double *)calloc(n + 1, sizeof(double));
    for (k = 0; k < n; k++)
    {
        Par[k] = -1;
        Flag[k] = k;
        Lnz[k] = 0;
        for (p = Ap[k]; p < Ap[k+1]; p++)
        {
            for (i = Ai[p]; Flag[i] != k; i = Par[i])
            {
                if (Par[i] == -1) Par[i] = k;
                Lnz[i]++;
                Flag[i] = k;
            }
        }
    }
    lnzTotal = 0;
    for (k = 0; k < n; k++) { Lp[k] = lnzTotal; lnzTotal += Lnz[k]; }
    Lp[n] = lnzTotal;
    Li = (int *)malloc((lnzTotal + 1) * sizeof(int));
    Lx = (double *)malloc((lnzTotal + 1) * sizeof(double));
    Ux = (double *)malloc((lnzTotal + 1) * sizeof(double));
}

static void ldlNumeric(int n, double *dg)
{
    int    k, p, i, top, len, q;
    double yi, zi;
    for (k = 0; k < n; k++)
    {
        Y[k] = 0.0;
        Z[k] = 0.0;
        top = n;
        Flag[k] = k;
        Lnz[k] = 0;
        for (p = Ap[k]; p < Ap[k+1]; p++)
        {
            i = Ai[p];
            Y[i] += Axu[p];            // K(i,k)
            Z[i] += Axl[p];            // K(k,i)
            for (len = 0; Flag[i] != k; i = Par[i])
            {
                Pat[len++] = i;
                Flag[i] = k;
            }
            while (len > 0) Pat[--top] = Pat[--len];
        }
        D[k] = dg[k];
        for (; top < n; top++)
        {
            i = Pat[top];
            yi = Y[i];
            zi = Z[i];
            Y[i] = 0.0;
            Z[i] = 0.0;
            for (q = Lp[i]; q < Lp[i] + Lnz[i]; q++)
            {
                Y[Li[q]] -= Lx[q] * yi;
                Z[Li[q]] -= Ux[q] * zi;
            }
            q = Lp[i] + Lnz[i];
            Li[q] = k;
            if (D[i] > 0.0)
            {
                Lx[q] = zi / D[i];
                Ux[q] = yi / D[i];
                D[k] -= Lx[q] * yi;
            }
            else Lx[q] = Ux[q] = 0.0;
            Lnz[i]++;
        }
        if (D[k] <= 1.0e-13 * dg[k] || D[k] < 1.0e-14) D[k] = 0.0;  // isolated dry cell
    }
}

static void ldlSolve(int n, double *b)
{
    int k, p;
    for (k = 0; k < n; k++)
        for (p = Lp[k]; p < Lp[k] + Lnz[k]; p++) b[Li[p]] -= Lx[p] * b[k];
    for (k = 0; k < n; k++) b[k] = (D[k] > 0.0) ? b[k] / D[k] : 0.0;
    for (k = n - 1; k >= 0; k--)
        for (p = Lp[k]; p < Lp[k] + Lnz[k]; p++) b[k] -= Ux[p] * b[Li[p]];
}

//-----------------------------------------------------------------------------
//  Nested Newton on V1(eta) - V2(eta) + T eta = b
//-----------------------------------------------------------------------------
static double faceFlow(TFace *f, double *da, double *db)
//
//  Q = Q0 + a etaL - b etaR, except that a face whose receiving side sits below
//  the crest cannot run backward.
//
{
    double etaL = Cell[f->L].eta, etaR = Cell[f->R].eta, x;
    double aa = f->a, bb = f->b;

    x = f->Q0 + aa * etaL - bb * etaR;
    if ((f->dir > 0 && x < 0.0) || (f->dir < 0 && x > 0.0))
    {
        x = 0.0; aa = 0.0; bb = 0.0;
    }
    *da = aa;
    *db = bb;
    return x;
}

static void fluxes(double dt, double theta)
//
//  Puts the face terms of the cell equations into Res, and their derivatives
//  into Etap (diagonal) and Axu, Axl (off diagonal).
//
{
    int    i, p, u, v;
    double x, aa, bb, w = dt * theta;
    TFace *f;
    for (i = 0; i < Ne; i++) { Axu[i] = 0.0; Axl[i] = 0.0; }
    for (i = 0; i < Nc; i++) { Res[i] = 0.0; Etap[i] = 0.0; }
    for (i = 0; i < Nf; i++)
    {
        f = &Face[i];
        x = w * faceFlow(f, &aa, &bb);
        Res[f->L] += x;
        Res[f->R] -= x;
        Etap[f->L] += w * aa;
        Etap[f->R] += w * bb;
        if (f->edge < 0) continue;
        p = EdgePos[f->edge];
        u = Cell[f->L].unk;
        v = Cell[f->R].unk;
        if (u < v)
        {
            Axu[p] -= w * bb;          // K(L,R), row u column v
            Axl[p] -= w * aa;          // K(R,L)
        }
        else
        {
            Axu[p] -= w * aa;          // K(R,L), row v column u
            Axl[p] -= w * bb;          // K(L,R)
        }
    }
}

static double cellTol(int i, double slope)
//
//  Volume tolerance: a fixed floor, or what the rounding of eta allows when the
//  cell has a large area or large conveyance attached.
//
{
    return VTOL + 2.0e-15 * fabs(Cell[i].eta) * (fabs(slope) + Etap[i]);
}

static double residual(double dt, double theta, int *ok)
{
    int    i;
    double r, rmax = 0.0;
    fluxes(dt, theta);
    *ok = TRUE;
    for (i = 0; i < Nc; i++) if (Cell[i].unk >= 0)
    {
        r = fabs(Res[i] + cellV(&Cell[i], Cell[i].eta) - Rhs[i]);
        rmax = MAX(rmax, r);
        if (r > cellTol(i, TFLOOD * (Cell[i].eta >= Cell[i].etaTop - 1.0))) *ok = FALSE;
    }
    return rmax;
}

static int plainNewton(double dt, double theta)
//
//  Plain Newton from the warm start. The solution of the system is unique, so
//  any iterate that closes the volume balance is the answer. HEC reports that
//  Newton can fail under pressure; when it does nestedNewton takes over.
//
{
    int    i, k, l, done;
    TCell *c;
    TTab  *t;
    double x, p, rmax = 0.0;

    for (l = 0; l < 8; l++)
    {
        fluxes(dt, theta);
        rmax = 0.0;
        done = TRUE;
        for (i = 0; i < Nc; i++)
        {
            c = &Cell[i];
            if (c->unk < 0) continue;
            t = c->tab;
            x = c->eta - c->shift;
            k = tabFind(t, x, &c->hint);
            if (k < 0)
            {
                Res[i] -= Rhs[i];
                p = 0.0;
                Diag[c->unk] = (Etap[i] > 0.0) ? Etap[i] : t->t1[0];
            }
            else
            {
                Res[i] += t->v1[k] - t->v2[k] +
                          (t->t1[k] - t->t2[k]) * (x - t->e[k]) - Rhs[i];
                p = MAX(t->t1[k] - t->t2[k], 0.0);
                if (p <= 0.0 && Etap[i] <= 0.0) p = t->t1[k];   // above a dry crown
                Diag[c->unk] = p + Etap[i];
            }
            rmax = MAX(rmax, fabs(Res[i]));
            if (fabs(Res[i]) > cellTol(i, p)) done = FALSE;
            X[c->unk] = Res[i];
        }
        StatInner += 1.0;
        if (done) { MaxRes = MAX(MaxRes, rmax); return TRUE; }
        ldlNumeric(Nun, Diag);
        StatFact += 1.0;
        ldlSolve(Nun, X);
        for (i = 0; i < Nc; i++) if (Cell[i].unk >= 0)
        {
            Cell[i].eta -= X[Cell[i].unk];
            if (Cell[i].eta < Cell[i].zMin - ETAFLOOR)
                Cell[i].eta = Cell[i].zMin - ETAFLOOR;
        }
    }
    return FALSE;
}

static int nestedNewton(double dt, double theta)
//
//  Casulli & Zanolli (2012). V = V1 - V2, both convex. The outer loop freezes
//  V2 as a tangent and climbs monotonically from below; the inner loop is Newton
//  on the convex remainder. Each cell starts at or below the elevation where
//  dV/d(eta) first turns down, so the first tangent of V2 is flat. Without that
//  start the diagonal can go negative and the iteration stalls.
//
{
    int    i, m, l, k, done = FALSE;
    TCell *c;
    TTab  *t;
    double x, rmax = 1.0e30, v1, p1;

    StatNested += 1.0;

    for (i = 0; i < Nc; i++)
    {
        c = &Cell[i];
        if (c->unk < 0) continue;
        x = c->tab->ePk + c->shift;
        c->eta = EtaPrev[i];
        if (c->eta < c->zMin) c->eta = c->zMin;
        if (c->eta > x) c->eta = x;
    }
    for (m = 0; m < MAXOUTER; m++)
    {
        // --- freeze the concave part at the current iterate
        for (i = 0; i < Nc; i++)
        {
            c = &Cell[i];
            if (c->unk < 0) continue;
            t = c->tab;
            x = c->eta - c->shift;
            k = tabFind(t, x, &c->hint);
            Etak[i] = c->eta;
            if (k < 0) { V2k[i] = 0.0; P2k[i] = 0.0; }
            else
            {
                V2k[i] = t->v2[k] + t->t2[k] * (x - t->e[k]);
                P2k[i] = t->t2[k];
            }
        }
        StatOuter += 1.0;

        // --- Newton on the convex part
        for (l = 0; l < MAXINNER; l++)
        {
            fluxes(dt, theta);
            rmax = 0.0;
            done = TRUE;
            for (i = 0; i < Nc; i++)
            {
                c = &Cell[i];
                if (c->unk < 0) continue;
                t = c->tab;
                x = c->eta - c->shift;
                k = tabFind(t, x, &c->hint);
                if (k < 0) { v1 = 0.0; p1 = 0.0; }
                else
                {
                    v1 = t->v1[k] + t->t1[k] * (x - t->e[k]);
                    p1 = t->t1[k];
                }
                Res[i] += v1 - V2k[i] - P2k[i] * (c->eta - Etak[i]) - Rhs[i];
                rmax = MAX(rmax, fabs(Res[i]));
                if (fabs(Res[i]) > cellTol(i, p1)) done = FALSE;
                // --- a sealed run of full cells has no storage at all, so its
                //     block is singular. The small area gives Newton a direction
                //     to raise the whole run until a manhole floods.
                x = p1 - P2k[i];
                Diag[c->unk] = MAX(x, SEALAREA) + Etap[i];
                X[c->unk] = Res[i];
            }
            StatInner += 1.0;
            if (done) break;
            ldlNumeric(Nun, Diag);
            StatFact += 1.0;
            ldlSolve(Nun, X);
            for (i = 0; i < Nc; i++) if (Cell[i].unk >= 0)
            {
                Cell[i].eta -= X[Cell[i].unk];
                if (Cell[i].eta < Cell[i].zMin - ETAFLOOR)
                    Cell[i].eta = Cell[i].zMin - ETAFLOOR;
                if (Cell[i].eta > Cell[i].zMin + ETACEIL)
                    Cell[i].eta = Cell[i].zMin + ETACEIL;
            }
        }
        rmax = residual(dt, theta, &done);
        if (done) break;

        // --- no movement means this linearization has no solution: a sealed,
        //     full stretch with a closed exit. The next trial reopens the exit.
        x = 0.0;
        for (i = 0; i < Nc; i++) if (Cell[i].unk >= 0)
            x = MAX(x, fabs(Cell[i].eta - Etak[i]));
        if (x < 1.0e-9) break;
    }
    if (!done) StatFail++;
    MaxRes = MAX(MaxRes, rmax);
    return done;
}

//-----------------------------------------------------------------------------
//  Faces
//-----------------------------------------------------------------------------
static void faceOpen(TFace *f)
//
//  A face that is dry at the linearization point would be a wall, and a front
//  moving more than a cell per step would fill a cell with no way out, leaving
//  the head nowhere to go but out of a manhole. So a dry face opens as soon as
//  the level upstream passes its invert, at about critical velocity. The next
//  trial sees it wet and replaces this with the real face. It takes OPENDEPTH of
//  water to open: without that dead band a rounding error in a dry cell becomes
//  a flow, and the next dry cell, with no width to hold it, turns it into a
//  large level.
//
{
    TPipe *p;
    int    j;
    double c, de, open;
    if (f->kind != 0 || f->a != 0.0 || f->b != 0.0) return;
    if (f->Qs != 0.0 || f->Cn != 0.0) return;
    p = &Pipe[f->pipe];
    j = p->link;
    if (Link[j].setting == 0.0) return;
    de = Cell[f->L].etaLin - Cell[f->R].etaLin;
    c  = p->barrels * p->aFull * sqrt(GRAVITY / p->yFull);
    open = (RasPipeCourant > 0.0) ? OPENDEPTH : 0.0;   // 0 reproduces version 1.0
    if (de >= 0.0)
    {
        f->a   = c;
        f->Q0  = -c * (f->z + open);
        f->dir = 1;
    }
    else if (!Link[j].hasFlapGate)
    {
        f->b   = c;
        f->Q0  = c * (f->z + open);
        f->dir = -1;
    }
}

static void faceConduit(TFace *f, double dt, double theta)
{
    TPipe  *p  = &Pipe[f->pipe];
    int     j  = p->link, k = p->k;
    int     n1 = Link[j].node1, n2 = Link[j].node2;
    double  etaL = Cell[f->L].etaLin, etaR = Cell[f->R].etaLin;
    double  de = etaR - etaL;
    double  up = MAX(etaL, etaR), dn = MIN(etaL, etaR);
    double  y  = up - f->z;
    double  A, R, cf, B, B0, s, u, dudB, gdx, C, G, Q, Qc, w, phi = 1.0;
    int     normal;

    f->A = 0.0; f->u = 0.0; f->a = 0.0; f->b = 0.0; f->Q0 = 0.0; f->dir = 0;
    f->Qs = 0.0; f->Cn = 0.0;
    if (y <= DRYDEPTH || Link[j].setting == 0.0)
    {
        faceOpen(f);
        return;
    }
    A = geoA(p, y);

    // --- in a sloping cell a flat level overstates the depth at the low face.
    //     The face area is the lesser of the area at that level and the mean
    //     area of the water upstream, which also lets a thin film drain.
    {
        int    fromL = (etaL >= etaR);
        TCell *cu    = fromL ? &Cell[f->L] : &Cell[f->R];
        int    pc    = fromL ? f->pcL : f->pcR;
        double aAvg  = A;
        if (cu->node < 0)
            aAvg = cellV(cu, up) / (p->barrels * p->delta);
        else if (pc >= 0)
            aAvg = pieceV(p, up, Piece[pc].z0, Piece[pc].z1, Piece[pc].len) /
                   Piece[pc].len;
        if (aAvg < A)
        {
            A = aAvg;
            y = geoYofA(p, A);
            if (cu->node < 0)
            {
                TTab *t = cu->tab;
                int   q = tabFind(t, up - cu->shift, &cu->hint);
                w = geoW(p, y);
                if (q >= 0 && w > 0.0)
                    phi = (t->t1[q] - t->t2[q]) / (p->barrels * p->delta) / w;
            }
        }
    }
    if (A <= 0.0) return;
    R = MAX(geoR(p, y), RMIN);

    // --- friction coefficient per unit velocity (1/ft)
    if (Link[j].xsect.type == FORCE_MAIN && y >= p->yFull)
    {
        u  = MAX(fabs(f->u), 0.01);
        u  = MAX(u, fabs(f->uOld));
        cf = forcemain_getFricSlope(j, u, R) / u;
    }
    else cf = Conduit[k].roughFactor / pow(R, 1.33333333333);
    cf += f->K / (2.0 * f->dx);

    gdx = GRAVITY * dt / f->dx;
    B = f->F - gdx * (theta * de + (1.0 - theta) * f->deOld);
    if (f->I > 0.0)                    // full equations
    {
        s = sqrt(f->I * f->I + 4.0 * dt * cf * fabs(B));
        u = 2.0 * B / (f->I + s);
        dudB = 1.0 / s;
    }
    else                               // diffusion wave: Manning, exactly
    {
        B0 = GRAVITY * dt * SLOPE0;
        s  = sqrt(1.0 / (dt * cf));
        if (fabs(B) >= B0)
        {
            u = SGN(B) * s * sqrt(fabs(B));
            dudB = 0.5 * s / sqrt(fabs(B));
        }
        else
        {
            dudB = s / sqrt(B0);
            u = dudB * B;
        }
    }
    C = p->barrels * A * gdx * theta * dudB;
    Q = p->barrels * A * u;

    // --- a normal flow outfall: the friction slope is the conduit slope, and
    //     the face is a control that looks only at the level behind it
    normal = (f->bc == 2 && fabs(Conduit[k].slope) > 0.0);
    if (normal)
    {
        Q = p->barrels * A * sqrt(GRAVITY * fabs(Conduit[k].slope) / cf);

        // --- normal depth tops out at the crown, as in SWMM. Above that the
        //     outfall holds the crown and head, not slope, drives the flow.
        B = gdx * (up - f->z - p->yFull);
        if (B > 0.0)
        {
            if (f->I > 0.0)
            {
                s = sqrt(f->I * f->I + 4.0 * dt * cf * B);
                u = 2.0 * B / (f->I + s);
                dudB = 1.0 / s;
            }
            else
            {
                s = sqrt(1.0 / (dt * cf));
                u = s * sqrt(B);
                dudB = 0.5 * s / sqrt(B);
            }
            if (p->barrels * A * u > Q)
            {
                Q = p->barrels * A * u;
                C = p->barrels * A * gdx * theta * dudB;
                normal = FALSE;
            }
        }
        if (Cell[f->R].unk >= 0) Q = -Q;
    }

    // --- how the flow changes with the wetted area at the upstream level
    G = 0.0;
    if (y < p->yFull && Q * (etaL - etaR) >= 0.0)
    {
        if (f->I > 0.0) G = fabs(Q) * geoDA(p, y) / A * phi;
        else            G = fabs(Q) * geoDK(p, y) * phi;
        G = MAX(G, 0.0);

        // --- never so steep that the tangent turns the flow around before
        //     the upstream cell runs dry
        G = MIN(G, fabs(Q) / MAX(up - f->z, DRYDEPTH));
    }

    if (normal) C = 0.01 * G;

    // --- closed flap gates block a face
    if ((f->idx == 0 || f->idx == p->nf - 1) && link_setFlapGate(j, n1, n2, Q))
        return;

    // --- flow over a drop cannot exceed critical flow at the crest; there the
    //     face acts as a control and the downstream level no longer matters
    //     Water drawn out of a node starts from rest, so it can't enter the
    //     conduit faster than critical either, drop or no drop. Diffusion wave
    //     has no inertia to tell it that.
    if ((f->crest && dn <= f->z) ||
        (f->I <= 0.0 && (f->idx == 0 || f->idx == p->nf - 1) &&
         Cell[etaL >= etaR ? f->L : f->R].node >= 0))
    {
        w  = geoW(p, y);
        Qc = (w > 0.0) ? p->barrels * A * sqrt(GRAVITY * A / w) : fabs(Q);

        // --- leaving a steep pipe the flow is already supercritical, so the
        //     end is held to normal flow, not critical (SWMM takes the lesser
        //     of the two depths at an outfall, the same thing)
        if (Cell[etaL >= etaR ? f->L : f->R].node < 0)
            Qc = MAX(Qc, p->barrels * A * sqrt(GRAVITY * fabs(Conduit[k].slope) / cf));
        if (fabs(Q) > Qc)
        {
            G = (y < p->yFull) ? 1.5 * Qc * w / A : 0.0;
            C = 0.01 * G;              // keeps the row of a dry neighbor alive
            Q = SGN(Q) * Qc;
        }
    }

    // --- user flow limit and culvert inlet control work on the first face,
    //     the way a gate does: the face delivers that flow and no more
    if (f->idx == 0)
    {
        Link[j].inletControl = FALSE;
        Qc = fabs(Q);
        if (Link[j].qLimit > 0.0) Qc = MIN(Qc, Link[j].qLimit * p->barrels);
        // --- the first face can sit below the culvert's inlet invert when the
        //     end cell borrows the top of the pipe, and the FHWA equations have
        //     no meaning for a head below the inlet
        if (Link[j].xsect.culvertCode > 0 && y < p->yFull && Q > 0.0 &&
            etaL > Node[n1].invertElev + Link[j].offset1)
            Qc = MIN(Qc, p->barrels * culvert_getInflow(j, Q / p->barrels, etaL));
        if (Qc < fabs(Q))
        {
            C = 0.0;
            G = 0.0;
            Q = SGN(Q) * Qc;
        }
    }

    f->A = A;
    f->a = C;
    f->b = C;
    f->Qs = Q;
    f->Cn = C;
    if (etaL >= etaR) f->a += G; else f->b += G;
    f->Q0 = Q - f->a * etaL + f->b * etaR;

    // --- water cannot come back over a crest the receiving side is below
    f->dir = 0;
    if (Q > 0.0 && etaR <= f->z) f->dir = 1;
    if (Q < 0.0 && etaL <= f->z) f->dir = -1;
}

static void faceSecant(TFace *f)
//
//  Fallback form of a face: Q = C (etaL - etaR) with the same C on both sides,
//  the way HEC changes the friction of a gate face to deliver a flow. The cell
//  system is then a symmetric M-matrix with a right side >= 0, so a solution
//  with V >= 0 exists and the nested Newton theory applies as published.
//
{
    double de = Cell[f->L].etaLin - Cell[f->R].etaLin, c;
    f->dir = 0;
    if (f->kind == 2)
    {
        f->a = 0.0;
        f->b = 0.0;
        f->Q0 = MAX(f->Qs, 0.0);
        return;
    }
    c = (fabs(de) > 1.0e-6) ? f->Qs / de : f->Cn;
    if (c < 0.0) c = 0.0;
    f->a = c;
    f->b = c;
    f->Q0 = 0.0;
    faceOpen(f);
}

static void faceOther(TFace *f, double dt, int trial)
{
    int    j = f->link, n1, n2, m, curve;
    double q, q1, q2, y, qMax, d = 0.001;

    n1 = Link[j].node1;
    n2 = Link[j].node2;
    Link[j].dqdh = 0.0;
    q  = link_getInflow(j);
    f->a = 0.0;
    f->b = 0.0;

    // --- which links can be differentiated
    curve = (f->kind == 1);
    if (Link[j].type == PUMP)
    {
        m = Pump[Link[j].subIndex].pumpCurve;
        if (m >= 0 && (Curve[m].curveType == PUMP3_CURVE ||
                       Curve[m].curveType == PUMP4_CURVE ||
                       Curve[m].curveType == PUMP5_CURVE)) curve = TRUE;
    }
    if (curve)
    {
        y = Node[n1].newDepth;
        Node[n1].newDepth = y + d;
        q1 = link_getInflow(j);
        Node[n1].newDepth = y;
        y = Node[n2].newDepth;
        Node[n2].newDepth = y + d;
        q2 = link_getInflow(j);
        Node[n2].newDepth = y;
        q = link_getInflow(j);
        f->a = MAX((q1 - q) / d, 0.0);
        f->b = MAX((q - q2) / d, 0.0);
    }

    // --- pumps and dummy links: limited by water available at the inlet
    if (f->kind == 2 && Node[n1].type != OUTFALL)
    {
        qMax = Node[n1].inflow + Node[n1].overflow + Cell[n1].vOld / dt;
        if (q > qMax) { q = MAX(qMax, 0.0); f->a = 0.0; f->b = 0.0; }
        q = MAX(q, 0.0);
    }
    f->Q0 = q - f->a * Cell[f->L].etaLin + f->b * Cell[f->R].etaLin;

    // --- a regulator cannot draw back from a dry cell; pumps run one way
    f->dir = 0;
    if (f->kind == 1)
    {
        if (q > 0.0 && Cell[f->R].unk >= 0 && Cell[f->R].etaLin <= Cell[f->R].zMin)
            f->dir = 1;
        if (q < 0.0 && Cell[f->L].unk >= 0 && Cell[f->L].etaLin <= Cell[f->L].zMin)
            f->dir = -1;
    }
    else f->dir = 1;
    f->Qs = q;
    f->Cn = MAX(f->a, f->b);
    (void)trial;
}

//-----------------------------------------------------------------------------
//  Keep SWMM's node records in step with the cells
//-----------------------------------------------------------------------------
static double shaftV(int i, double eta);

static void syncDepths(void)
{
    int i;
    double y;
    for (i = 0; i < Nobjects[NODE]; i++)
    {
        if (Node[i].type == OUTFALL) continue;
        y = Cell[i].etaLin - Node[i].invertElev;
        Node[i].newDepth = MAX(y, 0.0);
        if (NeedVol[i]) Node[i].newVolume = shaftV(i, Cell[i].etaLin);
    }
}

static void updateNodeFlows(int useMean)
{
    int    i;
    double q;
    TFace *f;
    for (i = 0; i < Nobjects[NODE]; i++)
    {
        Node[i].inflow = 0.0;
        Node[i].outflow = Node[i].losses;
        if (Node[i].newLatFlow >= 0.0) Node[i].inflow += Node[i].newLatFlow;
        else Node[i].outflow -= Node[i].newLatFlow;
    }
    for (i = 0; i < Nf; i++)
    {
        f = &Face[i];
        q = useMean ? f->Qbar : f->Q;
        if (f->L < Npc)
        {
            if (q >= 0.0) Node[f->L].outflow += q; else Node[f->L].inflow -= q;
        }
        if (f->R < Npc)
        {
            if (q >= 0.0) Node[f->R].inflow += q; else Node[f->R].outflow -= q;
        }
    }
}

static void setRhs(double dt, double theta)
{
    int    i;
    double flux;
    for (i = 0; i < Nc; i++) Rhs[i] = Cell[i].vOld + dt * Cell[i].src;
    if (theta < 1.0) for (i = 0; i < Nf; i++)
    {
        flux = dt * (1.0 - theta) * Face[i].Qold;
        Rhs[Face[i].L] -= flux;
        Rhs[Face[i].R] += flux;
    }
}

static void limitPumps(double dt)
//
//  Pumps are the only explicit sinks. Keep each cell's right side >= 0.
//
{
    int    i;
    double cut;
    TFace *f;
    for (i = 0; i < Nf; i++)
    {
        f = &Face[i];
        if (f->kind != 2) continue;
        Rhs[f->L] -= dt * f->Q0;
        Rhs[f->R] += dt * f->Q0;
    }
    for (i = 0; i < Nf; i++)
    {
        f = &Face[i];
        if (f->kind != 2 || Rhs[f->L] >= 0.0) continue;
        cut = MIN(f->Q0, -Rhs[f->L] / dt);
        f->Q0 -= cut;
        Rhs[f->L] += dt * cut;
        Rhs[f->R] -= dt * cut;
    }
    for (i = 0; i < Nf; i++)
    {
        f = &Face[i];
        if (f->kind != 2) continue;
        Rhs[f->L] += dt * f->Q0;
        Rhs[f->R] -= dt * f->Q0;
    }
}

static int trimDemand(double dt)
//
//  A negative lateral flow at a cell that has run dry, with nothing able to
//  reach it this step, has no solution. The demand that can't be met is dropped
//  for the rest of the step and stays out of the volume ledger.
//
{
    int    i, n = 0;
    double r;
    TCell *c;
    fluxes(dt, 1.0);
    for (i = 0; i < Nc; i++)
    {
        c = &Cell[i];
        if (c->unk < 0 || c->src >= 0.0 || c->eta >= c->zMin) continue;
        r = Res[i] - Rhs[i];
        if (r <= 0.0) continue;
        r = MIN(r, -c->src * dt);
        c->src += r / dt;
        Rhs[i] += r;
        n++;
    }
    for (i = 0; i < Nc; i++) EtaPrev[i] = MAX(Cell[i].eta, Cell[i].zMin);
    return n;
}

//-----------------------------------------------------------------------------
//  Public functions
//-----------------------------------------------------------------------------
static int isTrue(int j)
{
    return Link[j].type == CONDUIT && Link[j].xsect.type != DUMMY;
}

static int canBorrow(int n, double offset)
{
    return Node[n].type != OUTFALL && fabs(offset) < 1.0e-6;
}

static int dblCmp(const void *x, const void *y)
{
    double a = *(const double *)x, b = *(const double *)y;
    return (a < b) ? -1 : (a > b);
}

static double shaftV(int i, double eta)
{
    double d = eta - Node[i].invertElev;
    double v;
    if (d <= 0.0) return 0.0;
    v = node_getVolume(i, MIN(d, Node[i].fullDepth));
    if (d > Node[i].fullDepth && Cell[i].canPond)
        v += (d - Node[i].fullDepth) * Node[i].pondedArea;
    return v;
}

static double piecesV(int i, double eta)
{
    int pc;
    double v = 0.0;
    for (pc = PieceHead[i]; pc >= 0; pc = Piece[pc].next)
        v += pieceV(&Pipe[Piece[pc].pipe], eta, Piece[pc].z0, Piece[pc].z1,
                    Piece[pc].len) * Pipe[Piece[pc].pipe].barrels;
    return v;
}

static void buildNodeTable(int i)
{
    TCell  *c = &Cell[i];
    TTab   *t = &Tabs[Ntabs++];
    TPiece *q;
    double  zlo, zhi, top, d, v;
    double *e;
    int     n = 0, cap = 64, m, k, pc;

    e = (double *)malloc(cap * sizeof(double));
#define ADDE(val) do { if (n == cap) { cap *= 2; \
        e = (double *)realloc(e, cap * sizeof(double)); } e[n++] = (val); } while (0)

    ADDE(Node[i].invertElev);
    ADDE(Node[i].invertElev + Node[i].fullDepth);
    top = Node[i].invertElev + Node[i].fullDepth;
    if (!c->canPond) top += Node[i].surDepth;
    ADDE(top);
    c->etaTop = top;
    if (Node[i].type == STORAGE)
        for (m = 1; m < 48; m++)
            ADDE(Node[i].invertElev + Node[i].fullDepth * m / 48.0);
    for (pc = PieceHead[i]; pc >= 0; pc = Piece[pc].next)
    {
        q = &Piece[pc];
        zlo = MIN(q->z0, q->z1);
        zhi = MAX(q->z0, q->z1);
        d = Pipe[q->pipe].yFull;
        k = (int)ceil((zhi - zlo + d) / (d / 16.0));
        k = MAX(k, 8);
        k = MIN(k, 64);
        for (m = 0; m <= k; m++) ADDE(zlo + (zhi - zlo + d) * m / k);
    }
    qsort(e, n, sizeof(double), dblCmp);
    for (m = k = 0; m < n; m++)
        if (m == 0 || e[m] - e[k-1] > 1.0e-7) e[k++] = e[m];
    n = k;

    tabAlloc(t, n);
    for (m = 0; m < n; m++)
    {
        t->e[m] = e[m];
        v = shaftV(i, e[m]) + piecesV(i, e[m]);
        if (!c->canPond && e[m] > top) v += TFLOOD * (e[m] - top);
        t->v[m] = v;
    }
    tabSplit(t, c->canPond ? Node[i].pondedArea : TFLOOD);
    free(e);
    c->tab = t;
    c->shift = 0.0;
    c->zMin = t->e[0];
}

static void buildPipeTable(TPipe *p)
{
    TTab  *t = &Tabs[Ntabs++];
    double dz = fabs(p->z2 - p->z1) * p->delta / p->L, d = p->yFull;
    int    k, m;
    k = (int)ceil((dz + d) / (d / 32.0));
    k = MAX(k, 16);
    k = MIN(k, 128);
    tabAlloc(t, k + 1);
    for (m = 0; m <= k; m++)
    {
        t->e[m] = -0.5 * dz + (dz + d) * m / k;
        t->v[m] = pieceV(p, t->e[m], -0.5 * dz, 0.5 * dz, p->delta) * p->barrels;
    }
    t->v[0] = 0.0;
    tabSplit(t, 0.0);
    for (m = 0; m < p->nc; m++)
    {
        Cell[p->c0 + m].tab = t;
        Cell[p->c0 + m].zMin = t->e[0] + Cell[p->c0 + m].shift;
        Cell[p->c0 + m].etaTop = 1.0e30;
    }
}

static double totalVolume(void)
{
    int i;
    double v = 0.0;
    for (i = 0; i < Nc; i++) if (Cell[i].unk >= 0) v += cellV(&Cell[i], Cell[i].eta);
    return v;
}

static void setStoredVolumes(void)
//
//  Purpose: divides each cell's volume between SWMM's node and link records.
//           Volume is read from the cell table so the totals stay exact.
//
{
    int    i, j, pc;
    double vs, vp, tot, sc;
    TCell *c;
    for (j = 0; j < Nobjects[LINK]; j++) if (isTrue(j)) Link[j].newVolume = 0.0;
    for (j = 0; j < Np; j++) Pipe[j].vp1 = Pipe[j].vp2 = 0.0;
    for (i = Npc; i < Nc; i++)
    {
        c = &Cell[i];
        Link[Pipe[c->pipe].link].newVolume += cellV(c, c->eta);
    }
    for (i = 0; i < Npc; i++)
    {
        c = &Cell[i];
        if (Node[i].type == OUTFALL) continue;
        vs  = shaftV(i, c->eta);
        tot = vs + piecesV(i, c->eta);
        sc  = (tot > 0.0) ? cellV(c, c->eta) / tot : 0.0;
        Node[i].newVolume = vs * sc;
        if (!c->canPond && Node[i].newVolume > Node[i].fullVolume)
            Node[i].newVolume = Node[i].fullVolume;
        for (pc = PieceHead[i]; pc >= 0; pc = Piece[pc].next)
        {
            vp = pieceV(&Pipe[Piece[pc].pipe], c->eta, Piece[pc].z0, Piece[pc].z1,
                        Piece[pc].len) * Pipe[Piece[pc].pipe].barrels;
            Link[Pipe[Piece[pc].pipe].link].newVolume += vp * sc;
            if (Link[Pipe[Piece[pc].pipe].link].node1 == i)
                Pipe[Piece[pc].pipe].vp1 += vp * sc;
            else Pipe[Piece[pc].pipe].vp2 += vp * sc;
        }
    }
}

//=============================================================================

static void projectStages(void)
//
//  HEC's Use Initial Stage: the first value at a stage boundary is projected up
//  the conduits as a flat water surface, so the boundary doesn't send a surge
//  into an empty network in the first step. It stops at anything that isn't an
//  open conduit, at a flap gate, and at the top of a manhole.
//
{
    int    i, j, k, n1, n2, changed, m;
    double h, zi1, zi2, *H;
    TPipe *p;

    if (!RasPipeInitStage || Fhotstart1.mode == USE_FILE) return;
    H = (double *)malloc(Npc * sizeof(double));
    for (i = 0; i < Npc; i++) H[i] = -1.0e30;
    for (j = 0; j < Nobjects[LINK]; j++)
    {
        if (Node[Link[j].node2].type == OUTFALL)
            node_setOutletDepth(Link[j].node2, 0.0, 0.0, Link[j].offset2);
        else if (Node[Link[j].node1].type == OUTFALL)
            node_setOutletDepth(Link[j].node1, 0.0, 0.0, Link[j].offset1);
    }
    for (i = 0; i < Npc; i++)
    {
        if (Node[i].type != OUTFALL) continue;
        m = Outfall[Node[i].subIndex].type;
        if (m != FIXED_OUTFALL && m != TIDAL_OUTFALL && m != TIMESERIES_OUTFALL) continue;
        if (Outfall[Node[i].subIndex].hasFlapGate || Node[i].newDepth <= 0.0) continue;
        H[i] = Node[i].invertElev + Node[i].newDepth;
    }
    do
    {
        changed = FALSE;
        for (k = 0; k < Np; k++)
        {
            p = &Pipe[k];
            j = p->link;
            if (Link[j].hasFlapGate || Link[j].setting == 0.0) continue;
            n1 = Link[j].node1;
            n2 = Link[j].node2;
            zi1 = Node[n1].invertElev + Link[j].offset1;
            zi2 = Node[n2].invertElev + Link[j].offset2;
            h = MAX(H[n2] > zi2 ? H[n2] : -1.0e30, H[n1] > zi1 ? H[n1] : -1.0e30);
            if (h <= -1.0e29) continue;
            for (i = 0; i < p->nc; i++)
            {
                TCell *c = &Cell[p->c0 + i];
                if (h > c->zMin && h > c->eta) c->eta = h;
            }
            if (h > zi1 && h > H[n1] && Node[n1].type != OUTFALL) { H[n1] = h; changed = TRUE; }
            if (h > zi2 && h > H[n2] && Node[n2].type != OUTFALL) { H[n2] = h; changed = TRUE; }
        }
    } while (changed);
    for (i = 0; i < Npc; i++)
    {
        if (Node[i].type == OUTFALL || H[i] <= Cell[i].eta) continue;
        Cell[i].eta = MIN(H[i], Cell[i].etaTop);
    }
    free(H);
}

void raspipe_init(void)
{
    int    i, j, k, n1, n2, m, nCells, nFaces, nPieces, cc, ff, pc, pp;
    int    b1, b2, *ea;
    double L, a, b, delta, z1, z2, x, dx, h1, h2, cellLen;
    TPipe *p;
    TEdge *e;
    int    ne;

    // --- junctions: the manhole is the node's base area
    for (i = 0; i < Nobjects[NODE]; i++)
    {
        if (Node[i].fullDepth > 1.0e5) Node[i].fullDepth = 1.0e5;
        if (Node[i].surDepth > 1.0e5) Node[i].surDepth = 1.0e5;
        if (Node[i].type != STORAGE && Node[i].type != OUTFALL &&
            !(Node[i].fullVolume > 0.0))
            Node[i].fullVolume = MinSurfArea * Node[i].fullDepth;
    }

    // --- count the mesh
    Npc = Nobjects[NODE];
    Np = 0; nCells = Npc; nFaces = 0; nPieces = 0;
    NCapped = 0;
    cellLen = RasPipeCellLen;
    for (j = 0; j < Nobjects[LINK]; j++)
    {
        if (isTrue(j))
        {
            Np++;
            L = link_getLength(j);
            a = canBorrow(Link[j].node1, Link[j].offset1) ? 0.5 : 0.0;
            b = canBorrow(Link[j].node2, Link[j].offset2) ? 0.5 : 0.0;
            m = (int)floor(L / cellLen - a - b + 0.5);
            m = MAX(m, 1);
            if (m > RasPipeMaxCells) NCapped++;
            m = MIN(m, RasPipeMaxCells);
            nCells += m;
            nFaces += m + 1;
            nPieces += (a > 0.0) + (b > 0.0);
        }
        else nFaces++;
    }
    Nc = nCells; Nf = nFaces;
    Cell  = (TCell *)calloc(Nc + 1, sizeof(TCell));
    Face  = (TFace *)calloc(Nf + 1, sizeof(TFace));
    Pipe  = (TPipe *)calloc(Np + 1, sizeof(TPipe));
    Piece = (TPiece *)calloc(nPieces + 1, sizeof(TPiece));
    Tabs  = (TTab *)calloc(Npc + Np + 1, sizeof(TTab));
    Ntabs = 0;
    Rhs  = (double *)calloc(Nc + 1, sizeof(double));
    Res  = (double *)calloc(Nc + 1, sizeof(double));
    Diag = (double *)calloc(Nc + 1, sizeof(double));
    X    = (double *)calloc(Nc + 1, sizeof(double));
    V2k  = (double *)calloc(Nc + 1, sizeof(double));
    P2k  = (double *)calloc(Nc + 1, sizeof(double));
    Etak = (double *)calloc(Nc + 1, sizeof(double));
    Etap = (double *)calloc(Nc + 1, sizeof(double));
    EtaPrev = (double *)calloc(Nc + 1, sizeof(double));
    QPrev   = (double *)calloc(Nf + 1, sizeof(double));
    NodeConv = (char *)calloc(Npc + 1, sizeof(char));
    NeedVol  = (char *)calloc(Npc + 1, sizeof(char));
    PieceHead = (int *)malloc((Npc + 1) * sizeof(int));
    for (i = 0; i <= Npc; i++) PieceHead[i] = -1;

    // --- node cells carry the same index as the node
    for (i = 0; i < Npc; i++)
    {
        Cell[i].node = i;
        Cell[i].pipe = -1;
        Cell[i].canPond = (AllowPonding && Node[i].pondedArea > 0.0);
    }

    // --- mesh each conduit
    cc = Npc; ff = 0; pc = 0; pp = 0;
    for (j = 0; j < Nobjects[LINK]; j++)
    {
        if (!isTrue(j))
        {
            Face[ff].kind = (Link[j].type == ORIFICE || Link[j].type == WEIR ||
                             Link[j].type == OUTLET) ? 1 : 2;
            Face[ff].link = j;
            Face[ff].pipe = -1;
            Face[ff].L = Link[j].node1;
            Face[ff].R = Link[j].node2;
            Face[ff].Q = Link[j].newFlow;
            Face[ff].edge = -1;
            if (Link[j].type == PUMP) NeedVol[Link[j].node1] = 1;
            ff++;
            continue;
        }
        p = &Pipe[pp];
        k = Link[j].subIndex;
        n1 = Link[j].node1;
        n2 = Link[j].node2;
        L = link_getLength(j);
        b1 = canBorrow(n1, Link[j].offset1);
        b2 = canBorrow(n2, Link[j].offset2);
        a = b1 ? 0.5 : 0.0;
        b = b2 ? 0.5 : 0.0;
        m = (int)floor(L / cellLen - a - b + 0.5);
        m = MAX(m, 1);
        m = MIN(m, RasPipeMaxCells);
        delta = L / (a + m + b);
        z1 = Node[n1].invertElev + Link[j].offset1;
        z2 = Node[n2].invertElev + Link[j].offset2;
        p->link = j; p->k = k; p->L = L; p->delta = delta;
        p->z1 = z1; p->z2 = z2; p->barrels = Conduit[k].barrels;
        p->f0 = ff; p->nf = m + 1; p->c0 = cc; p->nc = m;
        geoBuild(p, &Link[j].xsect);
        p->qScale = 1.0e-3 * p->barrels * Link[j].qFull;
        h1 = Node[n1].invertElev + Node[n1].newDepth;
        h2 = Node[n2].invertElev + Node[n2].newDepth;

        for (i = 0; i < m; i++)        // interior cells
        {
            x = (a + i + 0.5) * delta;
            Cell[cc+i].node = -1;
            Cell[cc+i].pipe = pp;
            Cell[cc+i].shift = z1 + (z2 - z1) * x / L;
            if (Link[j].q0 != 0.0)
                Cell[cc+i].eta = Cell[cc+i].shift + Link[j].newDepth;
            else
            {
                Cell[cc+i].eta = h1 + (h2 - h1) * x / L;
                if (Cell[cc+i].eta <= Cell[cc+i].shift + FUDGE)
                    Cell[cc+i].eta = -1.0e20;     // dry; set to zMin below
            }
        }
        for (i = 0; i <= m; i++)       // faces
        {
            x = (a + i) * delta;
            dx = delta;
            if (i == 0) dx = (a + 0.5) * delta;
            if (i == m) dx = (b + 0.5) * delta;
            Face[ff+i].kind = 0;
            Face[ff+i].link = j;
            Face[ff+i].pipe = pp;
            Face[ff+i].idx = i;
            Face[ff+i].L = (i == 0) ? n1 : cc + i - 1;
            Face[ff+i].R = (i == m) ? n2 : cc + i;
            Face[ff+i].z = z1 + (z2 - z1) * x / L;
            Face[ff+i].dx = dx;
            Face[ff+i].K = Link[j].cLossAvg * dx / L;
            if (i == 0) Face[ff+i].K += Link[j].cLossInlet;
            if (i == m) Face[ff+i].K += Link[j].cLossOutlet;
            Face[ff+i].Q = Link[j].newFlow;
            Face[ff+i].edge = -1;
            Face[ff+i].pcL = -1;
            Face[ff+i].pcR = -1;
            Face[ff+i].bc = 0;
            Face[ff+i].crest = (i == 0 && !b1) || (i == m && !b2);
            if ((i == 0 && Node[n1].type == OUTFALL) ||
                (i == m && Node[n2].type == OUTFALL))
            {
                int nn = (i == 0) ? n1 : n2;
                if (Outfall[Node[nn].subIndex].type == FREE_OUTFALL)
                    Face[ff+i].bc = 1;
                if (Outfall[Node[nn].subIndex].type == NORMAL_OUTFALL)
                    Face[ff+i].bc = 2;
            }
        }
        if (b1)
        {
            Piece[pc].pipe = pp; Piece[pc].cell = n1;
            Piece[pc].z0 = z1; Piece[pc].z1 = Face[ff].z;
            Piece[pc].len = a * delta;
            Piece[pc].next = PieceHead[n1];
            PieceHead[n1] = pc;
            Face[ff].pcL = pc;
            pc++;
        }
        if (b2)
        {
            Piece[pc].pipe = pp; Piece[pc].cell = n2;
            Piece[pc].z0 = Face[ff+m].z; Piece[pc].z1 = z2;
            Piece[pc].len = b * delta;
            Piece[pc].next = PieceHead[n2];
            PieceHead[n2] = pc;
            Face[ff+m].pcR = pc;
            pc++;
        }
        cc += m; ff += m + 1; pp++;
    }
    Npieces = pc;

    // --- tables
    for (i = 0; i < Npc; i++)
        if (Node[i].type != OUTFALL) buildNodeTable(i);
    for (i = 0; i < Np; i++) buildPipeTable(&Pipe[i]);

    // --- initial levels
    for (i = 0; i < Npc; i++)
    {
        if (Node[i].type == OUTFALL) continue;
        if (Node[i].newDepth > FUDGE)
            Cell[i].eta = Node[i].invertElev + Node[i].newDepth;
        else Cell[i].eta = Cell[i].zMin;
    }
    for (i = Npc; i < Nc; i++) Cell[i].eta = MAX(Cell[i].eta, Cell[i].zMin);
    projectStages();

    // --- unknown numbering & matrix
    Nun = 0;
    for (i = 0; i < Nc; i++)
    {
        if (Cell[i].node >= 0 && Node[Cell[i].node].type == OUTFALL)
            Cell[i].unk = -1;
        else Cell[i].unk = Nun++;
    }
    ea = (int *)malloc((Nf + 1) * sizeof(int));
    e  = (TEdge *)malloc((Nf + 1) * sizeof(TEdge));
    ne = 0;
    for (i = 0; i < Nf; i++)
    {
        n1 = Cell[Face[i].L].unk;
        n2 = Cell[Face[i].R].unk;
        ea[i] = -1;
        if (n1 < 0 || n2 < 0 || n1 == n2) continue;
        e[ne].a = MIN(n1, n2);
        e[ne].b = MAX(n1, n2);
        ne++;
    }
    qsort(e, ne, sizeof(TEdge), edgeCmp);
    for (i = k = 0; i < ne; i++)
        if (i == 0 || edgeCmp(&e[i], &e[k-1]) != 0) e[k++] = e[i];
    Ne = k;
    for (i = 0; i < Nf; i++)
    {
        TEdge key, *hit;
        n1 = Cell[Face[i].L].unk;
        n2 = Cell[Face[i].R].unk;
        if (n1 < 0 || n2 < 0 || n1 == n2) continue;
        key.a = MIN(n1, n2);
        key.b = MAX(n1, n2);
        hit = (TEdge *)bsearch(&key, e, Ne, sizeof(TEdge), edgeCmp);
        Face[i].edge = (int)(hit - e);
    }
    ldlSymbolic(Nun, Ne, e);
    free(ea);
    free(e);
    for (i = 0; i < Nc; i++) if (Cell[i].unk >= 0) Cell[i].unk = Pinv[Cell[i].unk];

    // --- a junction that joins exactly two conduits hands momentum across
    {
        int *cnt = (int *)calloc(Npc + 1, sizeof(int));
        int *end = (int *)malloc((Npc + 1) * sizeof(int));
        int  a, b;
        for (i = 0; i < Npc; i++) end[i] = -1;
        for (i = 0; i < Nf; i++) Face[i].thru = -1;
        for (j = 0; j < Nobjects[LINK]; j++)
        {
            cnt[Link[j].node1]++;
            cnt[Link[j].node2]++;
        }
        for (k = 0; k < Np; k++)
        {
            p = &Pipe[k];
            for (m = 0; m < 2; m++)
            {
                n1 = m ? Link[p->link].node2 : Link[p->link].node1;
                if (Node[n1].type != JUNCTION || cnt[n1] != 2) continue;
                a = m ? p->f0 + p->nf - 1 : p->f0;
                b = end[n1];
                if (b < 0) { end[n1] = a; continue; }
                Face[a].thru = b;
                Face[b].thru = a;
                n2 = (Face[b].idx == 0) ? 0 : 1;   // which end of its conduit
                Face[a].thruSg = Face[b].thruSg = (n2 != m) ? 1.0 : -1.0;
            }
        }
        free(cnt);
        free(end);
    }

    // --- SWMM's stored volumes must equal the cell volumes from the start
    StatOuter = StatInner = StatFact = StatSteps = StatTrials = StatNested = 0.0;
    StatFallback = 0.0;
    StatFail = 0;
    StatUnsolved = 0;
    MaxRes = 0.0;
    setStoredVolumes();
    for (j = 0; j < Nobjects[LINK]; j++)
        if (isTrue(j)) Link[j].oldVolume = Link[j].newVolume;
    for (i = 0; i < Npc; i++) Node[i].oldVolume = Node[i].newVolume;
    for (i = 0; i < Nc; i++) Cell[i].etaLin = Cell[i].eta;
    VolIn = VolOut = VolFlood = 0.0;
    VolStart = totalVolume();
    FloodV = (double *)calloc(Npc + 1, sizeof(double));
    OutQ   = (double *)calloc(Nc + 1, sizeof(double));
    WarmScale = -1.0;
    WarmDone = FALSE;
    StatSub = 0.0;
    StatCr = StatDtMin = StatDtMax = StatTime = 0.0;
    QuietQ = QUIETFLOW;
    for (k = 0; k < Np; k++)
        QuietQ = MAX(QuietQ, 0.001 * Pipe[k].barrels * Link[Pipe[k].link].qFull);
    PipeOfLink = (int *)malloc(Nobjects[LINK] * sizeof(int));
    for (j = 0; j < Nobjects[LINK]; j++) PipeOfLink[j] = -1;
    for (k = 0; k < Np; k++)
    {
        PipeOfLink[Pipe[k].link] = k;
        Pipe[k].vp1Old = Pipe[k].vp1;
        Pipe[k].vp2Old = Pipe[k].vp2;
        Pipe[k].qUp = Pipe[k].qDn = 0.0;
    }
}

//=============================================================================

int raspipe_endFlows(int j, double *qUp, double *qDn)
//
//  Quality routing needs what crosses each end of a conduit. In dynamic wave a
//  conduit has one flow; here the two ends differ by the change in volume, and
//  each end sits where the borrowed piece of the pipe meets the manhole.
//
{
    if (!PipeOfLink || PipeOfLink[j] < 0) return FALSE;
    *qUp = Pipe[PipeOfLink[j]].qUp;
    *qDn = Pipe[PipeOfLink[j]].qDn;
    return TRUE;
}

//=============================================================================

int raspipe_nodeConverged(int i)
{
    return NodeConv[i];
}

//=============================================================================

static double backtrack(TPipe *p, TFace *f, double dt)
//
//  Input:   p = conduit, f = one of its faces, dt = pipe time step (sec)
//  Output:  returns V_X, the old velocity at the point the water now reaching
//           face f left dt seconds ago (ft/sec)
//  Purpose: HEC's explicit Eulerian-Lagrangian advection. For positive velocity
//
//              V_X = V_j - V* dt (V_j - V_j-1) / (x_j - x_j-1)
//              V*  = (V_j + V_j-1) / 2                 strong contraction
//              V*  = (A_j V_j + A_j-1 V_j-1) / (2 A_j) anywhere else
//
//           The first form keeps energy head constant, the second conserves
//           momentum. The walk moves one face interval at a time, so the
//           interpolation stays at Courant <= 1 however long the step is, and a
//           value interpolated between its neighbors can't blow up. The node at
//           the end of a conduit is water at rest, which leaves V_X = V (1 - Cr/2)
//           for water drawn into the pipe.
//
{
    int    k = f->idx, n;
    double s = (f->uOld >= 0.0) ? 1.0 : -1.0, tau = dt, vs, vUp, dx, dist;
    TFace *c, *g;

    for (;;)
    {
        c = &Face[p->f0 + k];
        n = k - (int)s;
        if (n < 0 || n >= p->nf)
        {
            // --- the conduit ends. Through a junction that joins only two
            //     conduits the water keeps going; anywhere else it is at rest.
            g   = NULL;
            vUp = 0.0;
            vs  = 0.5 * c->uOld;
            dx  = c->dx;
            if (c->thru >= 0)
            {
                TFace *o = &Face[c->thru];
                double u = c->thruSg * o->uOld;
                if (s * u > 0.0 && c->Am > 0.0)
                {
                    vUp = u;
                    if (o->Am > ACONTRACT * c->Am && s * (c->uOld - u) > 0.0)
                        vs = 0.5 * (c->uOld + u);
                    else vs = 0.5 * (c->Qold / p->barrels + c->thruSg * o->Qold /
                                     Pipe[o->pipe].barrels) / c->Am;
                    if (s * vs <= 0.0) return c->uOld;
                    dist = s * vs * tau;
                    return (dist <= dx) ? c->uOld + dist / dx * (u - c->uOld) : u;
                }
            }
        }
        else
        {
            g   = &Face[p->f0 + n];
            vUp = g->uOld;
            dx  = p->delta;
            if (c->Am <= 0.0) return c->uOld;
            if (g->Am > ACONTRACT * c->Am && s * (c->uOld - vUp) > 0.0)
                vs = 0.5 * (c->uOld + vUp);
            else vs = 0.5 * (c->Qold + g->Qold) / (p->barrels * c->Am);
        }
        if (s * vs <= 0.0) return c->uOld;
        dist = s * vs * tau;
        if (dist <= dx) return c->uOld + dist / dx * (vUp - c->uOld);
        if (g == NULL) return 0.0;
        tau -= dx / (s * vs);
        k = n;
    }
}

static int advance(double dt, int *isConverged)
//
//  Input:   dt = pipe time step (sec)
//  Output:  isConverged = TRUE if the head change between trials fell under
//           HEAD_TOLERANCE; returns the number of trials used
//  Purpose: advances the pipe network by one pipe time step.
//
{
    int    i, k, trial, trials = 0, converged = FALSE, solved = TRUE, nTrials;
    double theta = RasPipeTheta, thetaNow = theta, flux, dmax, r, tot, s;
    double qErr, omega;
    TCell *c;
    TFace *f;
    TPipe *p;

    // --- start of step
    for (i = 0; i < Nc; i++)
    {
        c = &Cell[i];
        c->etaOld = c->eta;
        c->src = 0.0;
        if (c->unk >= 0) c->vOld = cellV(c, c->eta);
    }
    for (i = 0; i < Npc; i++)
    {
        if (Node[i].type == OUTFALL) continue;
        Cell[i].src = 0.5 * (Node[i].oldLatFlow + Node[i].newLatFlow) - Node[i].losses;
        if (WarmScale >= 0.0) Cell[i].src = WarmScale * Node[i].newLatFlow;
    }

    // --- evaporation & seepage from conduits come out of the interior cells
    for (k = 0; k < Np; k++)
    {
        p = &Pipe[k];
        r = link_getLossRate(p->link, DW, 0.0, dt) * p->barrels;
        if (r <= 0.0) continue;
        tot = 0.0;
        for (i = 0; i < p->nc; i++) tot += Cell[p->c0 + i].vOld;
        if (tot <= 0.0)
        {
            Conduit[p->k].evapLossRate = 0.0;
            Conduit[p->k].seepLossRate = 0.0;
            continue;
        }

        // --- the interior cells can't lose more than they hold, and the
        //     books must show the rate that was actually taken
        if (r * dt > 0.99 * tot)
        {
            s = 0.99 * tot / (r * dt);
            r *= s;
            Conduit[p->k].evapLossRate *= s;
            Conduit[p->k].seepLossRate *= s;
        }
        for (i = 0; i < p->nc; i++)
            Cell[p->c0 + i].src -= r * Cell[p->c0 + i].vOld / tot;
    }

    for (k = 0; k < Np; k++)
    {
        Pipe[k].evapSum += Conduit[Pipe[k].k].evapLossRate * dt;
        Pipe[k].seepSum += Conduit[Pipe[k].k].seepLossRate * dt;
    }

    // --- old flows, and the explicit part of the momentum equation
    for (i = 0; i < Nf; i++)
    {
        f = &Face[i];
        f->Qold = f->Q;
        f->deOld = Cell[f->R].eta - Cell[f->L].eta;
        f->uOld = 0.0;
        if (f->kind == 0 && f->A > 0.0)
            f->uOld = f->Q / (Pipe[f->pipe].barrels * f->A);
    }
    if (RasPipeEqn != RASPIPE_DW) for (i = 0; i < Nf; i++)
    {
        f = &Face[i];
        if (f->kind != 0) continue;
        p = &Pipe[f->pipe];
        f->Am = 0.5 * (geoA(p, MAX(Cell[f->L].eta - f->z, 0.0)) +
                       geoA(p, MAX(Cell[f->R].eta - f->z, 0.0)));
    }
    for (i = 0; i < Nf; i++)
    {
        f = &Face[i];
        if (f->kind != 0) continue;
        if (RasPipeEqn == RASPIPE_DW)
        {
            f->I = 0.0;
            f->F = 0.0;
            continue;
        }

        // --- full equations: the acceleration is (V(n+1) - V_X(n)) / dt, and the
        //     solve in faceConduit keeps the friction implicit
        f->I = 1.0;
        f->F = (f->A > 0.0) ? backtrack(&Pipe[f->pipe], f, dt) : f->uOld;
    }

    // --- trials: friction, face areas, controls and outfalls follow the heads
    nTrials = MAXTRIALS;
    for (trial = 0; trial < nTrials || (!solved && trial < 2 * MAXTRIALS); trial++)
    {
        // --- an outfall holds its stage; free and normal outfalls hold nothing
        //     and their last face acts as the control, so nothing here depends
        //     on the flow of the previous trial
        for (i = 0; i < Nobjects[LINK]; i++)
        {
            if (Node[Link[i].node2].type == OUTFALL)
                node_setOutletDepth(Link[i].node2, 0.0, 0.0, Link[i].offset2);
            else if (Node[Link[i].node1].type == OUTFALL)
                node_setOutletDepth(Link[i].node1, 0.0, 0.0, Link[i].offset1);
        }
        for (i = 0; i < Npc; i++)
            if (Node[i].type == OUTFALL)
                Cell[i].eta = Node[i].invertElev + Node[i].newDepth;

        // --- point of linearization; the solve itself is never relaxed, so
        //     the flows stay exactly consistent with the volumes
        omega = (trial < 3) ? 1.0 : 0.5;
        for (i = 0; i < Nc; i++)
        {
            c = &Cell[i];
            if (trial == 0 || c->unk < 0) c->etaLin = c->eta;
            else c->etaLin += omega * (c->eta - c->etaLin);
        }
        syncDepths();

        for (i = 0; i < Nf; i++)
        {
            f = &Face[i];
            if (f->kind == 0) faceConduit(f, dt, theta);
            else faceOther(f, dt, trial);
        }

        for (i = 0; i < Nc; i++) EtaPrev[i] = Cell[i].eta;
        setRhs(dt, theta);

        // --- Newton on the linearized faces; if that fails, the secant form
        //     of the faces, which nested Newton is guaranteed to solve
        thetaNow = theta;
        solved = TRUE;
        if (RasPipeNestedOnly) solved = nestedNewton(dt, theta);
        else if (!plainNewton(dt, theta))
        {
            StatFallback += 1.0;
            thetaNow = 1.0;
            for (i = 0; i < Nf; i++) faceSecant(&Face[i]);
            setRhs(dt, 1.0);
            limitPumps(dt);
            solved = nestedNewton(dt, 1.0);
            if (!solved && trimDemand(dt)) solved = nestedNewton(dt, 1.0);
        }

        for (i = 0; i < Nf; i++)
        {
            f = &Face[i];
            f->Q = faceFlow(f, &r, &tot);
            if (f->kind == 0)
            {
                if (f->A > 0.0) f->u = f->Q / (Pipe[f->pipe].barrels * f->A);
            }
            else Link[f->link].newFlow = f->Q;
        }
        for (k = 0; k < Np; k++)
        {
            p = &Pipe[k];
            Link[p->link].newFlow = Face[p->f0 + p->nf / 2].Q;
        }
        updateNodeFlows(FALSE);

        trials++;
        dmax = 0.0;
        for (i = 0; i < Nc; i++) if (Cell[i].unk >= 0)
        {
            r = fabs(Cell[i].eta - EtaPrev[i]);
            dmax = MAX(dmax, r);
            if (i < Npc) NodeConv[i] = (r <= HeadTol);
        }
        qErr = 0.0;
        for (i = 0; i < Nf; i++)
        {
            f = &Face[i];
            if (f->kind != 0) continue;
            r = fabs(f->Q - QPrev[i]) / MAX(fabs(f->Q), 0.1 * Pipe[f->pipe].qScale);
            qErr = MAX(qErr, r);
            QPrev[i] = f->Q;
        }
        if (solved && trial > 0 && dmax <= HeadTol && qErr <= QTOL)
        {
            converged = TRUE;
            break;
        }
    }

    if (!solved) StatUnsolved++;

    // --- ledger of what the solve moved across the system boundary
    for (i = 0; i < Nc; i++) if (Cell[i].unk >= 0) VolIn += dt * Cell[i].src;
    for (i = 0; i < Nf; i++)
    {
        f = &Face[i];
        flux = dt * (thetaNow * f->Q + (1.0 - thetaNow) * f->Qold);
        if (Cell[f->R].unk < 0) VolOut += flux;
        if (Cell[f->L].unk < 0) VolOut -= flux;
    }

    // --- flow carried over this step, and water that left a manhole
    for (i = 0; i < Nf; i++) Face[i].Qsum += dt * Face[i].Q;
    for (i = 0; i < Npc; i++)
    {
        if (Node[i].type == OUTFALL) continue;
        c = &Cell[i];
        if (!c->canPond && c->eta > c->etaTop)
        {
            r = cellV(c, c->eta) - cellV(c, c->etaTop);
            FloodV[i] += r;
            VolFlood += r;
            c->eta = c->etaTop;
        }
    }
    for (i = 0; i < Nc; i++)
    {
        c = &Cell[i];
        if (c->unk >= 0 && c->eta < c->zMin) c->eta = c->zMin;
    }
    setStoredVolumes();
    for (i = 0; i < Nc; i++) Cell[i].etaLin = Cell[i].eta;
    syncDepths();
    *isConverged = converged;
    return trials;
}

static double courantRate(void)
//
//  HEC adjusts the pipe step from "estimated residence time Courant values" for
//  each cell. Residence time is what the cell holds over what leaves it, so this
//  returns the largest outflow / volume in the network (1/sec). A manhole with
//  no pipe piece in it holds next to nothing and would set the pace for
//  everything, so only cells that hold some pipe are counted, and a thin film
//  in a long cell is left out.
//
{
    int    i, n;
    double q, v, vf, rate = 0.0;
    TFace *f;
    TCell *c;
    for (i = 0; i < Nc; i++) OutQ[i] = 0.0;
    for (i = 0; i < Nf; i++)
    {
        f = &Face[i];
        q = f->Q;
        if (q > 0.0) OutQ[f->L] += q; else OutQ[f->R] -= q;
    }
    for (i = 0; i < Nc; i++)
    {
        c = &Cell[i];
        if (c->unk < 0 || OutQ[i] <= 0.0) continue;
        if (c->node >= 0 && PieceHead[c->node] < 0) continue;
        v = cellV(c, c->eta);
        if (c->node < 0)
        {
            n  = c->tab->n;
            vf = c->tab->v[n - 1];
            if (v < 0.01 * vf) continue;
        }
        else if (v < 1.0) continue;
        rate = MAX(rate, OutQ[i] / v);
    }
    return rate;
}

int raspipe_isQuiet(void)
//
//  TRUE when the target Courant number would allow the whole ROUTING_STEP and
//  next to nothing is arriving. HEC's base interval can be "reduced or increased",
//  and stock SWMM stretches its step through dry weather the same way.
//
{
    int i;
    if (RasPipeCourant <= 0.0 || Face == NULL || StatSteps == 0.0) return FALSE;
    for (i = 0; i < Npc; i++)
    {
        if (Node[i].type == OUTFALL) continue;
        if (fabs(Node[i].newLatFlow) > QuietQ ||
            fabs(Node[i].oldLatFlow) > QuietQ) return FALSE;
    }
    return courantRate() * RouteStep <= RasPipeCourant;
}

static int advanceAll(double tStep, int *isConverged)
//
//  Runs the pipe network across a routing step in as many pipe steps as the
//  target Courant number needs. The rest of SWMM never sees them. With
//  VARIABLE_STEP on, no pipe step runs longer than MAXMOVINGSTEP while water is
//  moving; that limit is what still resolves pumps and hydrographs.
//
{
    int    trials = 0, conv, allConv = TRUE;
    double t = 0.0, rem, dtS, r;
    double dtMin = MAX(MinRouteStep, MINSUBSTEP);

    NSub = 0;
    while (tStep - t > 1.0e-6)
    {
        rem = tStep - t;
        dtS = rem;
        r = courantRate();
        if (RasPipeCourant > 0.0)
        {
            if (r > 0.0) dtS = MAX(RasPipeCourant / r, dtMin);
            if (CourantFactor > 0.0 && dtS > MAXMOVINGSTEP && !raspipe_isQuiet())
                dtS = MAXMOVINGSTEP;
            if (dtS >= rem) dtS = rem;
            else if (2.0 * dtS > rem) dtS = 0.5 * rem;
        }
        StatCr = MAX(StatCr, r * dtS);
        StatDtMin = (StatDtMin > 0.0) ? MIN(StatDtMin, dtS) : dtS;
        StatDtMax = MAX(StatDtMax, dtS);
        StatTime += dtS;
        trials += advance(dtS, &conv);
        if (!conv) allConv = FALSE;
        t += dtS;
        NSub++;
    }
    StatSub += NSub;
    *isConverged = allConv;
    return trials;
}

static void clearSums(void)
{
    int i;
    for (i = 0; i < Nf; i++) Face[i].Qsum = 0.0;
    for (i = 0; i < Npc; i++) FloodV[i] = 0.0;
    for (i = 0; i < Np; i++) Pipe[i].evapSum = Pipe[i].seepSum = 0.0;
}

static void warmUp(double dt)
//
//  HEC's warm up: inflows come up over the first 2/3 of the period, then hold.
//  The clock does not move and nothing is reported. What ends up in the pipes is
//  the starting condition, so it goes to initial storage and not to inflow.
//
{
    int    m, conv, n = RasPipeWarmup;
    double v0 = totalVolume(), v1;

    WarmDone = TRUE;
    for (m = 1; m <= n; m++)
    {
        WarmScale = MIN(1.0, (double)m / (2.0 * n / 3.0));
        clearSums();
        advanceAll(dt, &conv);
    }
    WarmScale = -1.0;
    v1 = totalVolume();
    massbal_addInitStorage(v1 - v0);
    for (m = 0; m < Nobjects[LINK]; m++)
        if (isTrue(m)) Link[m].oldVolume = Link[m].newVolume;
    for (m = 0; m < Npc; m++) Node[m].oldVolume = Node[m].newVolume;
    VolIn = VolOut = VolFlood = 0.0;
    VolStart = v1;
    StatSub = 0.0;
    StatCr = StatDtMin = StatDtMax = StatTime = 0.0;
}

int raspipe_execute(double dt, int *isConverged)
//
//  Input:   dt = routing time step (sec)
//  Output:  isConverged = TRUE if every pipe step converged; returns the trials
//  Purpose: routes flow through the network over one routing step, then leaves
//           the mean flows in SWMM's records, so its totals see what really moved.
//
{
    int    i, k, trials;
    double r;
    TCell *c;
    TFace *f;
    TPipe *p;

    if (RasPipeWarmup > 0 && !WarmDone) warmUp(dt);
    clearSums();
    trials = advanceAll(dt, isConverged);

    for (i = 0; i < Nf; i++)
    {
        f = &Face[i];
        f->Qbar = (NSub == 1) ? f->Q : f->Qsum / dt;
        if (f->kind != 0) Link[f->link].newFlow = f->Qbar;
    }
    for (k = 0; k < Np; k++)
    {
        p = &Pipe[k];
        Link[p->link].newFlow = Face[p->f0 + p->nf / 2].Qbar;
        if (NSub > 1)
        {
            Conduit[p->k].evapLossRate = p->evapSum / dt;
            Conduit[p->k].seepLossRate = p->seepSum / dt;
        }
    }
    updateNodeFlows(TRUE);

    // --- flooding, then SWMM's node and link records
    for (i = 0; i < Npc; i++)
    {
        if (Node[i].type == OUTFALL) continue;
        Node[i].overflow = 0.0;
        if (!Cell[i].canPond && FloodV[i] > 0.0) Node[i].overflow = FloodV[i] / dt;
    }
    for (i = 0; i < Npc; i++)
    {
        if (Node[i].type == OUTFALL || !Cell[i].canPond) continue;
        r = (Node[i].newVolume - MAX(Node[i].oldVolume, Node[i].fullVolume)) / dt;
        Node[i].overflow = (r < FUDGE) ? 0.0 : r;
    }
    for (k = 0; k < Np; k++)
    {
        double a, y, v, aMid;
        p = &Pipe[k];
        f = &Face[p->f0 + p->nf / 2];
        Conduit[p->k].q1 = Face[p->f0].Qbar / p->barrels;
        Conduit[p->k].q2 = Face[p->f0 + p->nf - 1].Qbar / p->barrels;
        p->qUp = Face[p->f0].Qbar + (p->vp1 - p->vp1Old) / dt;
        p->qDn = Face[p->f0 + p->nf - 1].Qbar - (p->vp2 - p->vp2Old) / dt;
        p->vp1Old = p->vp1;
        p->vp2Old = p->vp2;
        Conduit[p->k].a1 = Face[p->f0].A;
        Conduit[p->k].a2 = Face[p->f0 + p->nf - 1].A;
        Conduit[p->k].fullState =
            link_getFullState(Conduit[p->k].a1, Conduit[p->k].a2, p->aFull);
        a = Link[p->link].newVolume / (p->L * p->barrels);
        if (a >= p->aFull) y = p->yFull;
        else y = (a > 0.0) ? xsect_getYofA(&Link[p->link].xsect, a) : 0.0;
        Link[p->link].newDepth = y;
        aMid = geoA(p, y);
        v = (aMid > 0.0) ? fabs(f->Qbar) / (p->barrels * aMid) : 0.0;
        Link[p->link].froude = link_getFroude(p->link, v, y);
        if (y <= FUDGE) Link[p->link].flowClass = DRY;
        else if (Link[p->link].froude > 1.0) Link[p->link].flowClass = SUPCRITICAL;
        else Link[p->link].flowClass = SUBCRITICAL;
    }

    for (i = 0; i < Nobjects[LINK]; i++) link_setOutfallDepth(i);

    StatSteps += 1.0;
    StatTrials += trials;
    return trials;
}

//=============================================================================

void raspipe_close(void)
//
//  Purpose: writes a solver summary to the report and frees all memory.
//
{
    int i;
    if (Cell == NULL) return;
    if (Frpt.file)
    {
        fprintf(Frpt.file, "\n  *******************");
        fprintf(Frpt.file, "\n  RASPIPE Pipe Solver");
        fprintf(Frpt.file, "\n  *******************");
        fprintf(Frpt.file, "\n  Version ................. 1.2 build %s", RASPIPE_BUILD);
        fprintf(Frpt.file, "\n  Equations ............... %s",
            RasPipeEqn == RASPIPE_DW ? "diffusion wave" : "full shallow water");
        fprintf(Frpt.file, "\n  Theta ................... %.3f", RasPipeTheta);
        fprintf(Frpt.file, "\n  Cell length ............. %.2f",
            RasPipeCellLen * UCF(LENGTH));
        {
            double *d = (double *)malloc((Np + 1) * sizeof(double));
            double t, lo = 0.0, hi = 0.0, med = 0.0;
            int    a, b;
            for (a = 0; a < Np; a++) d[a] = Pipe[a].delta;
            for (a = 1; a < Np; a++)   // insertion sort: few conduits are out of place
            {
                t = d[a];
                for (b = a - 1; b >= 0 && d[b] > t; b--) d[b + 1] = d[b];
                d[b + 1] = t;
            }
            if (Np > 0)
            {
                lo = d[0]; hi = d[Np - 1];
                med = (Np % 2) ? d[Np / 2] : 0.5 * (d[Np / 2 - 1] + d[Np / 2]);
            }
            free(d);
            fprintf(Frpt.file, "\n  Cell length achieved .... min %.2f, median %.2f, max %.2f",
                lo * UCF(LENGTH), med * UCF(LENGTH), hi * UCF(LENGTH));
            fprintf(Frpt.file, "\n  Conduits at cell limit .. %d of %d (limit %d)",
                NCapped, Np, RasPipeMaxCells);
        }
        fprintf(Frpt.file, "\n  Cells / faces ........... %d / %d", Nc, Nf);
        fprintf(Frpt.file, "\n  LDL nonzeros ............ %d", Lp[Nun]);
        if (StatSteps > 0.0)
        {
            double nPipe = MAX(StatSub, 1.0);
            fprintf(Frpt.file, "\n  Trials per step ......... %.2f",
                StatTrials / nPipe);
            fprintf(Frpt.file, "\n  Factorizations per step . %.2f",
                StatFact / nPipe);
        }
        fprintf(Frpt.file, "\n  Nested Newton solves .... %.0f", StatNested);
        fprintf(Frpt.file, "\n  Fallback solves ......... %.0f", StatFallback);
        {
            double vEnd = totalVolume();
            fprintf(Frpt.file, "\n  Volume ledger (ft3) ..... start %.3f + in %.3f"
                " - out %.3f - flood %.3f - end %.3f = %.3e",
                VolStart, VolIn, VolOut, VolFlood, vEnd,
                VolStart + VolIn - VolOut - VolFlood - vEnd);
        }
        fprintf(Frpt.file, "\n  Largest volume residual . %.3e ft3", MaxRes);
        fprintf(Frpt.file, "\n  Pipe steps per routing step %.2f", StatSub / MAX(StatSteps, 1.0));
        fprintf(Frpt.file, "\n  Pipe step (sec) ......... min %.3f, mean %.3f, max %.3f",
            StatDtMin, StatTime / MAX(StatSub, 1.0), StatDtMax);
        fprintf(Frpt.file, "\n  Largest Courant reached . %.3f", StatCr);
        fprintf(Frpt.file, "\n  Unconverged nested solves %d", StatFail);
        fprintf(Frpt.file, "\n  Steps left unsolved ..... %d\n", StatUnsolved);
    }
    for (i = 0; i < Ntabs; i++) tabFree(&Tabs[i]);
    FREE(Tabs); FREE(Cell); FREE(Face); FREE(Pipe); FREE(Piece); FREE(PieceHead);
    FREE(PipeOfLink); FREE(FloodV); FREE(OutQ);
    FREE(Rhs); FREE(Res); FREE(Diag); FREE(X); FREE(V2k); FREE(P2k); FREE(Etak);
    FREE(Etap); FREE(EtaPrev); FREE(QPrev); FREE(NodeConv); FREE(NeedVol);
    FREE(Perm); FREE(Pinv); FREE(Ap); FREE(Ai); FREE(Axu); FREE(Axl); FREE(EdgePos);
    FREE(Par); FREE(Flag); FREE(Lnz); FREE(Pat); FREE(Lp); FREE(D); FREE(Y); FREE(Z);
    FREE(Li); FREE(Lx); FREE(Ux);
}
