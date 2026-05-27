import { useEffect, useState } from 'react'
import { Lead, LeadStatus, LEAD_STATUS_LABELS, User, Tag } from '@/types'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { X, Filter } from 'lucide-react'

export interface FilterState {
  statuses: LeadStatus[]
  industries: string[]
  cities: string[]
  scoreMin: number
  scoreMax: number
  assignedTo: string[]
  tags: string[]  // tag names
}

export const EMPTY_FILTER: FilterState = {
  statuses: [],
  industries: [],
  cities: [],
  scoreMin: 0,
  scoreMax: 100,
  assignedTo: [],
  tags: [],
}

interface Props {
  leads: Lead[]
  users: User[]
  filter: FilterState
  onChange: (f: FilterState) => void
  tags?: Tag[]
}

function MultiSelect({
  options,
  selected,
  onToggle,
  label,
}: {
  options: { value: string; label: string }[]
  selected: string[]
  onToggle: (v: string) => void
  label: string
}) {
  return (
    <div className="mb-4">
      <Label className="text-xs text-muted-foreground mb-1 block">{label}</Label>
      <div className="flex flex-wrap gap-1">
        {options.map(opt => (
          <button
            key={opt.value}
            onClick={() => onToggle(opt.value)}
            className={`text-xs px-2 py-1 rounded-full border transition-colors ${
              selected.includes(opt.value)
                ? 'bg-primary text-primary-foreground border-primary'
                : 'border-input bg-white hover:bg-muted text-muted-foreground'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  )
}

export default function AdvancedFilterSidebar({ leads, users, filter, onChange, tags = [] }: Props) {
  // Derive unique industries and cities from leads
  const industries = [...new Set(leads.map(l => l.industry).filter(Boolean))] as string[]
  const cities = [...new Set(leads.map(l => l.city).filter(Boolean))] as string[]

  const toggle = <K extends 'statuses' | 'industries' | 'cities' | 'assignedTo' | 'tags'>(
    key: K,
    value: string
  ) => {
    const arr = filter[key] as string[]
    const next = arr.includes(value) ? arr.filter(v => v !== value) : [...arr, value]
    onChange({ ...filter, [key]: next })
  }

  const activeCount = [
    filter.statuses.length,
    filter.industries.length,
    filter.cities.length,
    filter.assignedTo.length,
    filter.tags?.length || 0,
    filter.scoreMin > 0 || filter.scoreMax < 100 ? 1 : 0,
  ].reduce((a, b) => a + b, 0)

  return (
    <div className="w-56 flex-shrink-0">
      <div className="bg-white border rounded-xl p-4 sticky top-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold flex items-center gap-1.5">
            <Filter className="w-3.5 h-3.5" /> 篩選
            {activeCount > 0 && (
              <span className="text-xs bg-primary text-primary-foreground rounded-full px-1.5">{activeCount}</span>
            )}
          </h3>
          {activeCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 text-xs text-muted-foreground"
              onClick={() => onChange(EMPTY_FILTER)}
            >
              清除
            </Button>
          )}
        </div>

        <MultiSelect
          label="狀態"
          options={Object.entries(LEAD_STATUS_LABELS).map(([k, v]) => ({ value: k, label: v }))}
          selected={filter.statuses}
          onToggle={v => toggle('statuses', v)}
        />

        {industries.length > 0 && (
          <MultiSelect
            label="產業"
            options={industries.map(i => ({ value: i, label: i }))}
            selected={filter.industries}
            onToggle={v => toggle('industries', v)}
          />
        )}

        {cities.length > 0 && (
          <MultiSelect
            label="城市"
            options={cities.map(c => ({ value: c, label: c }))}
            selected={filter.cities}
            onToggle={v => toggle('cities', v)}
          />
        )}

        {users.length > 0 && (
          <MultiSelect
            label="指派業務"
            options={users.map(u => ({ value: u.id, label: u.name }))}
            selected={filter.assignedTo}
            onToggle={v => toggle('assignedTo', v)}
          />
        )}

        {tags.length > 0 && (
          <div className="mb-4">
            <Label className="text-xs text-muted-foreground mb-1 block">標籤</Label>
            <div className="flex flex-wrap gap-1">
              {tags.map(tag => (
                <button
                  key={tag.id}
                  onClick={() => toggle('tags', tag.name)}
                  className={`text-xs px-2 py-1 rounded-full border transition-colors font-medium ${
                    (filter.tags || []).includes(tag.name)
                      ? 'text-white border-transparent'
                      : 'border-input bg-white text-muted-foreground hover:opacity-80'
                  }`}
                  style={
                    (filter.tags || []).includes(tag.name)
                      ? { backgroundColor: tag.color, borderColor: tag.color }
                      : {}
                  }
                >
                  {tag.name}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Score range */}
        <div className="mb-4">
          <Label className="text-xs text-muted-foreground mb-1 block">
            評分範圍：{filter.scoreMin} – {filter.scoreMax}
          </Label>
          <div className="space-y-2">
            <div>
              <Label className="text-xs">最低</Label>
              <input
                type="range"
                min={0}
                max={100}
                value={filter.scoreMin}
                onChange={e => onChange({ ...filter, scoreMin: Number(e.target.value) })}
                className="w-full accent-primary"
              />
            </div>
            <div>
              <Label className="text-xs">最高</Label>
              <input
                type="range"
                min={0}
                max={100}
                value={filter.scoreMax}
                onChange={e => onChange({ ...filter, scoreMax: Number(e.target.value) })}
                className="w-full accent-primary"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Filter Chips ──────────────────────────────────────────────────────────────

export function FilterChips({ filter, onChange }: { filter: FilterState; onChange: (f: FilterState) => void }) {
  const chips: { label: string; onRemove: () => void }[] = []

  filter.statuses.forEach(s =>
    chips.push({
      label: LEAD_STATUS_LABELS[s as LeadStatus] || s,
      onRemove: () => onChange({ ...filter, statuses: filter.statuses.filter(x => x !== s) }),
    })
  )
  filter.industries.forEach(i =>
    chips.push({
      label: i,
      onRemove: () => onChange({ ...filter, industries: filter.industries.filter(x => x !== i) }),
    })
  )
  filter.cities.forEach(c =>
    chips.push({
      label: c,
      onRemove: () => onChange({ ...filter, cities: filter.cities.filter(x => x !== c) }),
    })
  )

  if (filter.scoreMin > 0 || filter.scoreMax < 100) {
    chips.push({
      label: `評分 ${filter.scoreMin}-${filter.scoreMax}`,
      onRemove: () => onChange({ ...filter, scoreMin: 0, scoreMax: 100 }),
    })
  }
  ;(filter.tags || []).forEach(t =>
    chips.push({
      label: `#${t}`,
      onRemove: () => onChange({ ...filter, tags: (filter.tags || []).filter(x => x !== t) }),
    })
  )

  if (chips.length === 0) return null

  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {chips.map((chip, i) => (
        <span
          key={i}
          className="inline-flex items-center gap-1 text-xs bg-indigo-50 text-indigo-700 border border-indigo-200 rounded-full px-2 py-0.5"
        >
          {chip.label}
          <button onClick={chip.onRemove} className="hover:text-indigo-900">
            <X className="w-3 h-3" />
          </button>
        </span>
      ))}
    </div>
  )
}

// ── Apply filter to leads ─────────────────────────────────────────────────────

export function applyFilter(leads: Lead[], filter: FilterState): Lead[] {
  return leads.filter(lead => {
    if (filter.statuses.length > 0 && !filter.statuses.includes(lead.status)) return false
    if (filter.industries.length > 0 && !filter.industries.includes(lead.industry || '')) return false
    if (filter.cities.length > 0 && !filter.cities.includes(lead.city || '')) return false
    if (filter.assignedTo.length > 0 && !filter.assignedTo.includes(lead.assigned_to || '')) return false
    if (lead.score !== null) {
      if (lead.score < filter.scoreMin || lead.score > filter.scoreMax) return false
    }
    return true
  })
}
