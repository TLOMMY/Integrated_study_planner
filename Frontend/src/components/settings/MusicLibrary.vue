<script setup>
/**
 * 设置页 · 专注 · 我的音乐：导入本地歌曲、管理歌单（新建 / 重命名 / 删除 / 加减歌曲 / 排序 / 循环方式）。
 * 文件只存在本机 IndexedDB，不上传服务器。
 */
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { Icon } from '@iconify/vue'
import BottomSheet from '@/components/common/BottomSheet.vue'
import { useFocusStore } from '@/stores/focus'
import { useUiStore } from '@/stores/ui'
import { library, reloadLibrary } from '@/composables/useMusicLibrary'
import * as db from '@/utils/musicDb'
import { music, musicState } from '@/utils/musicPlayer'
import {
  ACCEPT, FORMATS_LABEL, MAX_FILE_BYTES, MAX_TOTAL_BYTES, NAME_MAX,
  addTracks, formatBytes, formatDuration, modeOf, moveTrack, nextMode, playlistKey, removeTrack,
} from '@/utils/music'

const focus = useFocusStore()
const ui = useUiStore()

const fileInput = ref(null)
const importing = ref('')
const expanded = ref(null)
const renaming = reactive({ kind: '', id: null, value: '' })
const picker = reactive({ open: false, playlist: null, picked: new Set() })

const usedBytes = computed(() => library.tracks.reduce((sum, t) => sum + (t.size || 0), 0))
const usedPercent = computed(() => Math.min(100, Math.round((usedBytes.value / MAX_TOTAL_BYTES) * 100)))
const trackById = computed(() => Object.fromEntries(library.tracks.map((t) => [t.id, t])))
const playlistTracks = (p) => p.trackIds.map((id) => trackById.value[id]).filter(Boolean)
const playlistSeconds = (p) => playlistTracks(p).reduce((sum, t) => sum + (t.duration || 0), 0)

onMounted(() => reloadLibrary())

// ---------------------------------------------------------------- 导入
const onFiles = async (event) => {
  const files = [...(event.target.files || [])]
  event.target.value = ''
  if (!files.length) return
  importing.value = `正在导入 ${files.length} 个文件…`
  try {
    const { added, failed } = await db.importFiles(files)
    await reloadLibrary()
    // 展开着某个歌单时，新导入的歌直接加进去
    const target = library.playlists.find((p) => p.id === expanded.value)
    if (target && added.length) await savePlaylist(addTracks(target, added.map((t) => t.id)))
    if (added.length) ui.success(`已导入 ${added.length} 首${target ? `，并加入「${target.name}」` : ''}`)
    failed.slice(0, 3).forEach((f) => ui.toast(f.reason, 'warning', 4200))
    if (failed.length > 3) ui.toast(`另有 ${failed.length - 3} 个文件导入失败`, 'warning', 4200)
  } catch (error) {
    ui.fail(error, '导入失败')
  } finally {
    importing.value = ''
  }
}

// ---------------------------------------------------------------- 歌单
const savePlaylist = async (playlist) => {
  try {
    await db.savePlaylist(playlist)
    await reloadLibrary()
  } catch (error) {
    ui.fail(error, '保存失败')
  }
}

const createPlaylist = async () => {
  try {
    const playlist = await db.createPlaylist(`歌单 ${library.playlists.length + 1}`)
    await reloadLibrary()
    expanded.value = playlist.id
    startRename('playlist', playlist)
  } catch (error) {
    ui.fail(error, '新建失败')
  }
}

const startRename = (kind, item) => Object.assign(renaming, { kind, id: item.id, value: item.name })
const commitRename = async () => {
  const { kind, id, value } = renaming
  if (!id) return
  Object.assign(renaming, { kind: '', id: null, value: '' })
  if (!value.trim()) return
  if (kind === 'playlist') {
    const playlist = library.playlists.find((p) => p.id === id)
    if (playlist && playlist.name !== value.trim()) await savePlaylist({ ...playlist, name: value })
  } else {
    await db.renameTrack(id, value).catch((error) => ui.fail(error))
    await reloadLibrary()
  }
}

const removePlaylist = async (playlist) => {
  const ok = await ui.confirm({ title: `删除歌单「${playlist.name}」？`, message: '歌单里的歌曲仍保留在「全部歌曲」里。', confirmText: '删除', danger: true })
  if (!ok) return
  if (focus.noiseKind === playlistKey(playlist.id)) focus.setNoise('off')
  await db.deletePlaylist(playlist.id).catch((error) => ui.fail(error))
  await reloadLibrary()
  ui.success('歌单已删除')
}

const cycleMode = (playlist) => {
  const mode = nextMode(playlist.mode)
  if (musicState.playlistId === playlist.id) music.setMode(mode)
  savePlaylist({ ...playlist, mode })
  ui.toast(modeOf(mode).label, 'info', 1400)
}

const openPicker = (playlist) => Object.assign(picker, { open: true, playlist, picked: new Set(playlist.trackIds) })
const togglePick = (id) => (picker.picked.has(id) ? picker.picked.delete(id) : picker.picked.add(id))
const applyPicker = async () => {
  const playlist = library.playlists.find((p) => p.id === picker.playlist?.id)
  picker.open = false
  if (!playlist) return
  // 保留原有顺序，取消勾选的移除，新勾选的追加到末尾
  const kept = { ...playlist, trackIds: playlist.trackIds.filter((id) => picker.picked.has(id)) }
  await savePlaylist(addTracks(kept, library.tracks.map((t) => t.id).filter((id) => picker.picked.has(id))))
}

// ---------------------------------------------------------------- 歌曲
const preview = reactive({ id: null, audio: null, url: null })
const stopPreview = () => {
  preview.audio?.pause()
  if (preview.url) URL.revokeObjectURL(preview.url)
  Object.assign(preview, { id: null, audio: null, url: null })
}
const togglePreview = async (track) => {
  if (preview.id === track.id) return stopPreview()
  stopPreview()
  const blob = await db.getBlob(track.id).catch(() => null)
  if (!blob) return ui.toast('这首歌的文件已不在本机', 'warning')
  const url = URL.createObjectURL(blob)
  const audio = new Audio(url)
  audio.volume = focus.noiseVolume * focus.noiseVolume
  audio.onended = stopPreview
  Object.assign(preview, { id: track.id, audio, url })
  audio.play().catch(() => {
    stopPreview()
    ui.toast('这首歌无法播放', 'warning')
  })
}
onBeforeUnmount(stopPreview)

const removeTrackFile = async (track) => {
  const used = library.playlists.filter((p) => p.trackIds.includes(track.id)).length
  const ok = await ui.confirm({
    title: `删除「${track.name}」？`,
    message: `将从本机删除这个文件${used ? `，并从 ${used} 个歌单中移除` : ''}。`,
    confirmText: '删除',
    danger: true,
  })
  if (!ok) return
  if (preview.id === track.id) stopPreview()
  await db.deleteTrack(track.id).catch((error) => ui.fail(error))
  await reloadLibrary()
}
</script>

<template>
  <div class="card mt-3 overflow-hidden" aria-labelledby="music-title">
    <div class="px-4 pt-3.5">
      <div class="flex items-center gap-3">
        <Icon icon="lucide:list-music" width="20" class="text-xp" />
        <span class="min-w-0 flex-1">
          <span id="music-title" class="block text-sm font-semibold text-ink">我的音乐</span>
          <span class="block text-[11px] text-ink-mute">导入本地歌曲做成歌单，专注时播放 · 仅保存在本设备，不会上传</span>
        </span>
      </div>
      <p v-if="library.error" class="mt-3 rounded-2xl bg-danger-light px-3 py-2 text-xs font-semibold text-danger">{{ library.error }}</p>
      <template v-else>
        <div class="mt-3">
          <div class="flex items-center justify-between text-[11px] font-semibold text-ink-mute">
            <span>已用 <b class="num text-ink-soft">{{ formatBytes(usedBytes) }}</b> / {{ formatBytes(MAX_TOTAL_BYTES) }} · {{ library.tracks.length }} 首</span>
            <span>单个文件 ≤ {{ formatBytes(MAX_FILE_BYTES) }}</span>
          </div>
          <div class="mt-1.5 h-1.5 overflow-hidden rounded-full bg-ink-line/70" role="progressbar" :aria-valuenow="usedPercent" aria-valuemin="0" aria-valuemax="100" aria-label="本机音乐占用空间">
            <div class="h-full rounded-full transition-all" :class="usedPercent > 90 ? 'bg-danger' : 'bg-xp'" :style="{ width: `${usedPercent}%` }" />
          </div>
        </div>
        <div class="mt-3 grid grid-cols-2 gap-2">
          <button class="btn-ghost py-2.5 text-xs" type="button" :disabled="Boolean(importing)" @click="fileInput.click()">
            <Icon :icon="importing ? 'lucide:loader-circle' : 'lucide:upload'" width="15" :class="importing && 'animate-spin'" />{{ importing || '导入歌曲' }}
          </button>
          <button class="btn-ghost py-2.5 text-xs" type="button" @click="createPlaylist"><Icon icon="lucide:list-plus" width="15" />新建歌单</button>
        </div>
        <p class="mt-1.5 text-[10px] text-ink-mute">支持 {{ FORMATS_LABEL }}（以浏览器能播放为准；.awv 按 wav 处理）。换设备或清除浏览器数据后需要重新导入。</p>
        <input ref="fileInput" type="file" class="hidden" :accept="ACCEPT" multiple aria-label="选择音频文件" @change="onFiles" />
      </template>
    </div>

    <!-- 歌单 -->
    <ul v-if="!library.error" class="mt-3 divide-y divide-ink-line/60 border-t border-ink-line/60" aria-label="歌单">
      <li v-if="library.loaded && !library.playlists.length" class="px-4 py-3 text-xs text-ink-mute">还没有歌单。新建一个，再把导入的歌加进去</li>
      <li v-for="p in library.playlists" :key="p.id">
        <div class="flex items-center gap-2 px-4 py-2.5">
          <button class="flex min-w-0 flex-1 items-center gap-2.5 text-left" type="button" :aria-expanded="expanded === p.id" @click="expanded = expanded === p.id ? null : p.id">
            <Icon icon="lucide:disc-3" width="18" :class="musicState.playlistId === p.id && musicState.playing ? 'animate-spin text-xp' : 'text-ink-mute'" />
            <span class="min-w-0 flex-1">
              <input
                v-if="renaming.kind === 'playlist' && renaming.id === p.id"
                v-model="renaming.value"
                class="field py-1 text-sm"
                :maxlength="NAME_MAX"
                aria-label="歌单名称"
                autofocus
                @click.stop
                @keydown.enter.prevent="commitRename"
                @keydown.esc.prevent="renaming.id = null"
                @blur="commitRename"
              />
              <span v-else class="block truncate text-sm font-bold text-ink">{{ p.name }}</span>
              <span class="num block text-[10px] text-ink-mute">{{ playlistTracks(p).length }} 首 · {{ formatDuration(playlistSeconds(p)) }} · {{ modeOf(p.mode).label }}</span>
            </span>
            <Icon :icon="expanded === p.id ? 'lucide:chevron-up' : 'lucide:chevron-down'" width="16" class="text-ink-mute" />
          </button>
        </div>
        <div v-if="expanded === p.id" class="bg-background/60 px-4 pb-3 pt-1">
          <div class="flex flex-wrap gap-1.5">
            <button class="chip" type="button" @click="openPicker(p)"><Icon icon="lucide:plus" width="13" />添加 / 移除歌曲</button>
            <button class="chip" type="button" :aria-label="`循环方式：${modeOf(p.mode).label}，点击切换`" @click="cycleMode(p)"><Icon :icon="modeOf(p.mode).icon" width="13" />{{ modeOf(p.mode).label }}</button>
            <button class="chip" type="button" @click="startRename('playlist', p)"><Icon icon="lucide:pencil" width="13" />重命名</button>
            <button class="chip border-danger/30 text-danger" type="button" @click="removePlaylist(p)"><Icon icon="lucide:trash-2" width="13" />删除</button>
          </div>
          <ol v-if="playlistTracks(p).length" class="mt-2 space-y-1">
            <li v-for="(t, i) in playlistTracks(p)" :key="t.id" class="flex items-center gap-2 rounded-xl bg-surface px-2.5 py-1.5">
              <span class="num w-5 text-center text-[11px] font-bold text-ink-mute">{{ i + 1 }}</span>
              <span class="min-w-0 flex-1 truncate text-xs font-semibold text-ink">{{ t.name }}</span>
              <span class="num text-[10px] text-ink-mute">{{ formatDuration(t.duration) }}</span>
              <button class="flex h-7 w-7 items-center justify-center rounded-full text-ink-mute hover:bg-background disabled:opacity-30" type="button" :disabled="i === 0" :aria-label="`上移：${t.name}`" @click="savePlaylist(moveTrack(p, p.trackIds.indexOf(t.id), -1))"><Icon icon="lucide:arrow-up" width="14" /></button>
              <button class="flex h-7 w-7 items-center justify-center rounded-full text-ink-mute hover:bg-background disabled:opacity-30" type="button" :disabled="i === playlistTracks(p).length - 1" :aria-label="`下移：${t.name}`" @click="savePlaylist(moveTrack(p, p.trackIds.indexOf(t.id), 1))"><Icon icon="lucide:arrow-down" width="14" /></button>
              <button class="flex h-7 w-7 items-center justify-center rounded-full text-ink-mute hover:bg-background hover:text-danger" type="button" :aria-label="`从歌单移除：${t.name}`" @click="savePlaylist(removeTrack(p, t.id))"><Icon icon="lucide:x" width="14" /></button>
            </li>
          </ol>
          <p v-else class="mt-2 text-[11px] text-ink-mute">歌单是空的：点「添加 / 移除歌曲」，或展开时直接「导入歌曲」会自动加入这个歌单</p>
        </div>
      </li>
    </ul>

    <!-- 全部歌曲 -->
    <details v-if="!library.error && library.tracks.length" class="border-t border-ink-line/60">
      <summary class="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-xs font-bold text-ink-soft">
        <Icon icon="lucide:music" width="15" class="text-ink-mute" />全部歌曲（{{ library.tracks.length }}）
        <Icon icon="lucide:chevron-down" width="14" class="ml-auto text-ink-mute" />
      </summary>
      <ul class="space-y-1 px-3 pb-3">
        <li v-for="t in library.tracks" :key="t.id" class="flex items-center gap-2 rounded-xl bg-background px-2.5 py-1.5">
          <button class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-surface text-primary" type="button" :aria-label="preview.id === t.id ? `停止试听：${t.name}` : `试听：${t.name}`" @click="togglePreview(t)">
            <Icon :icon="preview.id === t.id ? 'lucide:pause' : 'lucide:play'" width="13" />
          </button>
          <input
            v-if="renaming.kind === 'track' && renaming.id === t.id"
            v-model="renaming.value"
            class="field min-w-0 flex-1 py-1 text-xs"
            :maxlength="NAME_MAX"
            aria-label="歌曲名称"
            autofocus
            @keydown.enter.prevent="commitRename"
            @keydown.esc.prevent="renaming.id = null"
            @blur="commitRename"
          />
          <span v-else class="min-w-0 flex-1 truncate text-xs font-semibold text-ink">{{ t.name }}</span>
          <span class="num shrink-0 text-[10px] text-ink-mute">{{ formatDuration(t.duration) }} · {{ formatBytes(t.size) }}</span>
          <button class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-ink-mute hover:bg-surface" type="button" :aria-label="`重命名：${t.name}`" @click="startRename('track', t)"><Icon icon="lucide:pencil" width="13" /></button>
          <button class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-ink-mute hover:bg-surface hover:text-danger" type="button" :aria-label="`删除：${t.name}`" @click="removeTrackFile(t)"><Icon icon="lucide:trash-2" width="13" /></button>
        </li>
      </ul>
    </details>
  </div>

  <BottomSheet :open="picker.open" :title="`编辑「${picker.playlist?.name || ''}」`" subtitle="勾选要放进这个歌单的歌曲，新勾选的排在最后" @close="picker.open = false">
    <p v-if="!library.tracks.length" class="py-6 text-center text-xs text-ink-mute">还没有导入任何歌曲，先关闭这个窗口点「导入歌曲」</p>
    <ul v-else class="space-y-1.5 pb-2">
      <li v-for="t in library.tracks" :key="t.id">
        <label class="flex cursor-pointer items-center gap-3 rounded-2xl border px-3 py-2.5 transition" :class="picker.picked.has(t.id) ? 'border-primary bg-primary-light/50' : 'border-ink-line/70'">
          <input type="checkbox" class="h-4 w-4 accent-primary" :checked="picker.picked.has(t.id)" @change="togglePick(t.id)" />
          <span class="min-w-0 flex-1 truncate text-sm font-semibold text-ink">{{ t.name }}</span>
          <span class="num text-[11px] text-ink-mute">{{ formatDuration(t.duration) }}</span>
        </label>
      </li>
    </ul>
    <template #footer>
      <button class="btn-primary w-full" type="button" @click="applyPicker">保存（{{ picker.picked.size }} 首）</button>
    </template>
  </BottomSheet>
</template>
