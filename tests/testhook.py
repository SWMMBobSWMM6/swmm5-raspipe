import sys,shutil,os
src,dst,old=sys.argv[1],sys.argv[2],sys.argv[3]=='old'
if os.path.exists(dst): shutil.rmtree(dst)
shutil.copytree(src,dst)
p=dst+'/solver/raspipe.c'; s=open(p).read()
def R(a,b):
    global s
    assert a in s, a[:40]
    s=s.replace(a,b,1)
if not old:
    R('static const double ACONTRACT = 1.5;','static double ACONTRACT = 1.5;      ')
R("""        for (i = 0; i < m; i++)        // interior cells
        {
            x = (a + i + 0.5) * delta;
""","""        for (i = 0; i < m; i++)        // interior cells
        {
            x = (a + i + 0.5) * delta;
""")
R("""                if (Cell[cc+i].eta <= Cell[cc+i].shift + FUDGE)
                    Cell[cc+i].eta = -1.0e20;     // dry; set to zMin below
            }
""","""                if (Cell[cc+i].eta <= Cell[cc+i].shift + FUDGE)
                    Cell[cc+i].eta = -1.0e20;     // dry; set to zMin below
            }
            if (pp == 0 && getenv("RP_STEP"))     // TEST BUILD ONLY: a step in the water surface
            {
                double x0, hL, hR;
                sscanf(getenv("RP_STEP"), "%lf %lf %lf", &x0, &hL, &hR);
                Cell[cc+i].eta = Cell[cc+i].shift + (x < x0 ? hL : hR);
            }
""")
if not old:
    R("""    NCapped = 0;
""","""    NCapped = 0;
    if (getenv("RP_ACON")) ACONTRACT = atof(getenv("RP_ACON"));
""")
tm='StatTime' if not old else 'TestClock'
if old:
    R("static double  StatSub;\n","static double  StatSub;\nstatic double  TestClock;\n")
    R("""        trials += advance(dtS, &conv);
""","""        trials += advance(dtS, &conv);
        TestClock += dtS;
""")
else:
    pass
R("""        if (!conv) allConv = FALSE;
        t += dtS;
        NSub++;
""","""        if (!conv) allConv = FALSE;
        t += dtS;
        NSub++;
        {   // TEST BUILD ONLY: dump the cells of every conduit at RP_DUMP = "T file"
            static int done = 0;
            if (!done && getenv("RP_DUMP"))
            {
                double T; char name[256]; int a, b;
                sscanf(getenv("RP_DUMP"), "%lf %255s", &T, name);
                if (@@T@@ >= T - 1.0e-9)
                {
                    FILE *o = fopen(name, "w");
                    done = 1;
                    fprintf(o, "#T %.6f\\n", @@T@@);
                    for (a = 0; a < Np; a++)
                    {
                        TPipe *q = &Pipe[a];
                        for (b = 0; b < q->nc; b++)
                            fprintf(o, "c %d %d %.6f %.8f %.8f\\n", a, b, (b + 0.5 + (q->L/q->delta - q->nc)/2) * q->delta,
                                Cell[q->c0 + b].eta, Cell[q->c0 + b].shift);
                        for (b = 0; b < q->nf; b++)
                            fprintf(o, "f %d %d %.8f %.8f\\n", a, b, Face[q->f0 + b].Q, Face[q->f0 + b].A);
                    }
                    fclose(o);
                }
            }
        }
""".replace("@@T@@",tm))
if not old:
    R("""            else vs = 0.5 * (c->Qold + g->Qold) / (p->barrels * c->Am);
""","""            else vs = 0.5 * (c->Qold + g->Qold) / (p->barrels * (getenv("RP_AFACE") && c->A > 0.0 ? c->A : c->Am));
""")
open(p,'w').write(s)
