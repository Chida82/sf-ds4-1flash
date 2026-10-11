/* sf: the classification of every DS4_* switch and the startup report.
 *
 * Included by ds4.c only. ds4_env.def classifies every DS4_* name the sources
 * read (`make env-check` keeps it in step), and ds4_env_report() prints, once
 * per process, the set ones that are out of their normal state or that this
 * build never reads. */
#ifndef DS4_ENV_H
#define DS4_ENV_H

#include <stdio.h>
#include <string.h>

typedef struct {
    const char *name, *category, *state, *description;
} ds4_env_info;

static const ds4_env_info ds4_env_table[] = {
#define DS4_ENV(name, category, state, description) {#name, #category, #state, description},
#include "ds4_env.def"
#undef DS4_ENV
};

/* Walks the environment, not the table: with no DS4_* set it prints nothing. */
static void ds4_env_report(void) {
    extern char **environ;
    static int done;
    if (done) return;
    done = 1;
    const size_t n = sizeof(ds4_env_table) / sizeof(ds4_env_table[0]);
    for (char **e = environ; *e; e++) {
        const char *entry = *e;
        if (strncmp(entry, "DS4_", 4) != 0) continue;
        const size_t len = strcspn(entry, "=");
        const ds4_env_info *info = NULL;
        for (size_t j = 0; j < n && !info; j++) {
            if (strlen(ds4_env_table[j].name) == len && !strncmp(ds4_env_table[j].name, entry, len)) {
                info = &ds4_env_table[j];
            }
        }
        if (!info) {
            fprintf(stderr, "ds4: env %s is set but this build never reads it\n", entry);
        } else if (!strcmp(info->state, "unset")) {
            fprintf(stderr, "ds4: env %s is set (%s): %s\n", entry, info->category, info->description);
        }
    }
}

#endif
