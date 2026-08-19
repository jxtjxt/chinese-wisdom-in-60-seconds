import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Composition,
  Easing,
  Img,
  Sequence,
  interpolate,
  registerRoot,
  staticFile,
  useCurrentFrame,
} from 'remotion';
import story from '../storyboard.json';
import manifest from '../audio-manifest.json';
import audioResult from '../audio-result.json';
import publishing from '../publishing.json';
import {CenteredBlock} from './CenteredBlock';

const FPS = story.project.fps;
const PAPER = '#f7efd9';
const INK = '#29313a';
const CARD = 'rgba(255, 250, 236, 0.96)';
const ACCENT = '#d97835';
const scenes = story.scenes;
const segmentsById = Object.fromEntries(manifest.segments.map((segment) => [segment.id, segment]));
const resultsById = Object.fromEntries(audioResult.segments.map((segment) => [segment.id, segment]));
const starts = scenes.reduce((values, scene, index) => {
  values.push(index === 0 ? 0 : values[index - 1] + Math.round(scenes[index - 1].duration_sec * FPS));
  return values;
}, []);
const durationFrames = scenes.reduce((sum, scene) => sum + Math.round(scene.duration_sec * FPS), 0);

const publicPath = (record) => {
  const normalized = String(record.path || record.audio_file || '').replaceAll('\\', '/');
  const marker = normalized.toLowerCase().lastIndexOf('/public/');
  if (marker >= 0) return normalized.slice(marker + '/public/'.length);
  return normalized.replace(/^\/+/, '');
};

const timelineFor = (scene) => {
  let cursor = 0;
  return scene.segments.map((id) => {
    const segment = segmentsById[id];
    const result = resultsById[id];
    const start = Math.round(cursor * FPS);
    const duration = Number(result?.duration_sec || 0);
    cursor += duration + Number(segment?.pause_after_ms || 0) / 1000;
    return {segment, result, start, durationFrames: Math.max(1, Math.ceil(duration * FPS))};
  });
};

const imageMotion = (scene, frame, frames) => {
  const progress = interpolate(frame, [0, Math.max(1, frames - 1)], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.cubic),
  });
  if (scene.motion.type === 'scale') {
    return `scale(${interpolate(progress, [0, 1], [scene.motion.from_scale, scene.motion.to_scale])})`;
  }
  if (scene.motion.type === 'pan') {
    const x = interpolate(progress, [0, 1], [scene.motion.from_x_px, scene.motion.to_x_px]);
    const y = interpolate(progress, [0, 1], [scene.motion.from_y_px, scene.motion.to_y_px]);
    return `translate(${x}px, ${y}px)`;
  }
  return 'none';
};

const fadeOpacity = (frame, frames) => interpolate(
  frame,
  [0, 8, Math.max(9, frames - 8), frames],
  [0, 1, 1, 0],
  {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
);

const Caption = ({children, layout = {}}) => (
  <CenteredBlock
    bottom={layout.bottom ?? 210}
    width={layout.width ?? 648}
    style={{
      boxSizing: 'border-box', padding: '19px 26px', borderRadius: 29,
      background: 'rgba(39, 47, 55, 0.92)', color: '#fffaf0',
      fontFamily: 'Arial, "Noto Sans", sans-serif', fontSize: layout.font_size ?? 29,
      fontWeight: 750, lineHeight: 1.17, whiteSpace: 'pre-line',
      boxShadow: '0 12px 30px rgba(68, 50, 29, 0.18)',
    }}
  >{children}</CenteredBlock>
);

const PagedCaption = ({segment, layout}) => {
  const frame = useCurrentFrame();
  const pages = segment.caption_pages || [segment.text];
  const weights = pages.map((page) => Math.max(1, page.trim().split(/\s+/).length));
  const total = weights.reduce((sum, value) => sum + value, 0);
  const progress = frame / Math.max(1, Math.ceil(Number(resultsById[segment.id]?.duration_sec || 1) * FPS));
  let cumulative = 0;
  let selected = pages.length - 1;
  for (let index = 0; index < pages.length; index += 1) {
    cumulative += weights[index] / total;
    if (progress <= cumulative) { selected = index; break; }
  }
  return <Caption layout={layout}>{pages[selected]}</Caption>;
};

const Bubble = ({scene, segment}) => {
  const bubble = scene.bubble;
  const x = bubble.x * 1080;
  const y = bubble.y * 1920;
  const width = bubble.width * 1080;
  const anchorX = x + width / 2;
  const anchorY = y + 145;
  const targetX = bubble.tail_to.x * 1080;
  const targetY = bubble.tail_to.y * 1920;
  return <>
    <svg width="1080" height="1920" style={{position: 'absolute', inset: 0}}>
      <polygon points={`${anchorX - 15},${anchorY - 8} ${anchorX + 15},${anchorY - 8} ${targetX},${targetY}`} fill={CARD} stroke="#35404b" strokeWidth="4" strokeLinejoin="round" />
    </svg>
    <div style={{
      position: 'absolute', left: x, top: y, width, boxSizing: 'border-box',
      padding: '18px 22px', borderRadius: 28, background: CARD, border: '4px solid #35404b',
      color: INK, fontFamily: 'Arial, "Noto Sans", sans-serif', fontSize: bubble.font_size ?? 30,
      fontWeight: 760, lineHeight: 1.15, textAlign: 'center',
      boxShadow: '0 12px 28px rgba(68, 50, 29, 0.16)',
    }}>{segment.text}</div>
  </>;
};

const MeaningCard = ({scene}) => {
  const frame = useCurrentFrame();
  const timeline = timelineFor(scene);
  const startsByRole = Object.fromEntries(timeline.map((item) => [item.segment.spoken_role, item.start]));
  const reveal = (role) => interpolate(frame, [startsByRole[role] ?? 0, (startsByRole[role] ?? 0) + 12], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const card = story.project.meaning_card;
  const layout = card.layout || {};
  return (
    <CenteredBlock
      top={layout.top ?? 232}
      width={layout.width ?? 648}
      style={{
        boxSizing: 'border-box', padding: '32px 32px 29px', borderRadius: 40,
        background: CARD, border: '4px solid rgba(57, 65, 71, 0.82)', color: INK,
        fontFamily: 'Arial, "Noto Sans SC", "Microsoft YaHei", sans-serif',
        boxShadow: '0 18px 44px rgba(70, 53, 31, 0.16)',
      }}
    >
      <div style={{fontSize: layout.idiom_font_size ?? 82, fontWeight: 900, lineHeight: 1.05, opacity: reveal('idiom')}}>{story.project.idiom}</div>
      <div style={{fontSize: layout.pinyin_font_size ?? 37, fontWeight: 700, color: '#397783', marginTop: 12, opacity: reveal('idiom')}}>{story.project.pinyin}</div>
      <div style={{height: 4, background: '#e2a349', borderRadius: 2, margin: '24px auto', width: 180, opacity: reveal('meaning')}} />
      <div style={{fontSize: layout.meaning_font_size ?? 40, fontWeight: 800, lineHeight: 1.18, whiteSpace: 'pre-line', opacity: reveal('meaning')}}>{card.meaning_display || story.project.meaning}</div>
      <div style={{fontSize: layout.reflection_font_size ?? 33, fontWeight: 700, lineHeight: 1.2, color: ACCENT, marginTop: 25, whiteSpace: 'pre-line', opacity: reveal('reflection')}}>{card.reflection_display || card.reflection}</div>
      <div style={{fontSize: layout.source_font_size ?? 22, lineHeight: 1.25, marginTop: 23, color: '#5d625f', whiteSpace: 'pre-line', opacity: reveal('reflection')}}>{card.source}</div>
    </CenteredBlock>
  );
};

const SceneAudio = ({scene}) => <>{timelineFor(scene).map(({segment, result, start, durationFrames: frames}) => (
  <Sequence key={segment.id} from={start} durationInFrames={frames + 1}>
    <Audio src={staticFile(publicPath(result))} volume={1} />
  </Sequence>
))}</>;

const SceneText = ({scene}) => {
  if (scene.narrative_function === 'meaning') return <MeaningCard scene={scene} />;
  const timeline = timelineFor(scene);
  const dialogue = timeline.find(({segment}) => segment.kind === 'dialogue');
  if (dialogue) return <Bubble scene={scene} segment={dialogue.segment} />;
  return <>{timeline.filter(({segment}) => segment.kind === 'narration').map(({segment, start, durationFrames: frames}) => (
    <Sequence key={segment.id} from={start} durationInFrames={frames + 1}>
      <PagedCaption segment={segment} layout={scene.caption_layout} />
    </Sequence>
  ))}</>;
};

const CopyrightMark = ({mark}) => mark ? (
  <div style={{
    position: 'absolute', left: mark.x, top: mark.y,
    color: INK, opacity: mark.opacity, pointerEvents: 'none',
    fontFamily: 'Arial, "Helvetica Neue", sans-serif',
    fontSize: mark.font_size, fontWeight: 500, letterSpacing: 0.9,
    whiteSpace: 'nowrap', textShadow: '0 3px 3px rgba(255, 250, 236, 0.45)',
  }}>{mark.text}</div>
) : null;

const Scene = ({scene}) => {
  const frame = useCurrentFrame();
  const frames = Math.round(scene.duration_sec * FPS);
  return (
    <AbsoluteFill style={{backgroundColor: PAPER, overflow: 'hidden', opacity: fadeOpacity(frame, frames)}}>
      <Img src={staticFile(scene.image)} style={{width: 1080, height: 1920, objectFit: 'fill', transform: imageMotion(scene, frame, frames), transformOrigin: '50% 48%'}} />
      <SceneAudio scene={scene} />
      <SceneText scene={scene} />
      <CopyrightMark mark={scene.copyright_mark} />
    </AbsoluteFill>
  );
};

export const ChineseWisdomShort = () => (
  <AbsoluteFill style={{backgroundColor: PAPER}}>
    {publishing.music?.file ? <Audio src={staticFile(publishing.music.file)} loop volume={publishing.music.volume ?? 0.05} /> : null}
    {scenes.map((scene, index) => (
      <Sequence key={scene.id} from={starts[index]} durationInFrames={Math.round(scene.duration_sec * FPS)} premountFor={30}>
        <Scene scene={scene} />
      </Sequence>
    ))}
  </AbsoluteFill>
);

export const Cover = () => {
  const layout = publishing.cover.layout || {};
  return <AbsoluteFill style={{backgroundColor: PAPER, overflow: 'hidden'}}>
    <Img src={staticFile('images/cover-art.png')} style={{width: 1080, height: 1920, objectFit: 'fill'}} />
    <CenteredBlock
      top={layout.top ?? 570}
      width={layout.width ?? 648}
      style={{
        boxSizing: 'border-box', padding: '20px 24px 16px', borderRadius: 36,
        background: CARD, border: '4px solid #35404b', color: INK,
        fontFamily: 'Arial, "Noto Sans", sans-serif', fontSize: layout.font_size ?? 49,
        fontWeight: 950, lineHeight: 1.04, letterSpacing: 0.5, whiteSpace: 'pre-line',
        boxShadow: '0 14px 34px rgba(59, 45, 29, 0.18)',
      }}
    >
      {publishing.cover.title}
      <div style={{fontFamily: 'Arial, "Noto Sans SC", "Microsoft YaHei", sans-serif', fontSize: 30, color: ACCENT, marginTop: 9, letterSpacing: 3}}>{story.project.idiom}</div>
    </CenteredBlock>
  </AbsoluteFill>;
};

const Root = () => <>
  <Composition id="ChineseWisdomShort" component={ChineseWisdomShort} width={1080} height={1920} fps={FPS} durationInFrames={durationFrames} />
  <Composition id="Cover" component={Cover} width={1080} height={1920} fps={FPS} durationInFrames={1} />
</>;

registerRoot(Root);
