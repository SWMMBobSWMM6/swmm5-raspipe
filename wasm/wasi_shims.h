#ifndef WASI_SHIMS_H
#define WASI_SHIMS_H
#include <stdio.h>
#include <string.h>
/* no temp-file creation under WASI: make a name unique by a counter */
static inline int mkstemp(char *t){ static int n=0; char *x=strstr(t,"XXXXXX"); if(x){ snprintf(x,7,"%06d",++n);} return 0; }
#endif
