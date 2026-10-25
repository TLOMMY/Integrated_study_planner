<script setup>
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()
</script>

<template>
  <Transition enter-active-class="transition duration-150" enter-from-class="opacity-0" leave-active-class="transition duration-100" leave-to-class="opacity-0">
    <div v-if="ui.dialog" class="absolute inset-0 z-[80] flex items-center justify-center bg-scrim/45 px-8 backdrop-blur-[2px]" @click.self="ui.closeDialog(false)">
      <div class="w-full material max-w-sm animate-pop rounded-3xl bg-surface p-5 shadow-2xl" role="alertdialog" aria-modal="true">
        <h3 class="text-base font-black text-ink">{{ ui.dialog.title }}</h3>
        <p v-if="ui.dialog.message" class="mt-2 text-sm leading-6 text-ink-soft">{{ ui.dialog.message }}</p>
        <div class="mt-5 grid grid-cols-2 gap-3">
          <button class="btn-ghost" type="button" @click="ui.closeDialog(false)">{{ ui.dialog.cancelText }}</button>
          <button :class="ui.dialog.danger ? 'btn bg-danger text-on-danger' : 'btn-primary'" type="button" @click="ui.closeDialog(true)">
            {{ ui.dialog.confirmText }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>
