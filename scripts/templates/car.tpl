  <g transform="translate($anchor_x,$anchor_y)">
    <g>
      <animateTransform attributeName="transform" type="translate" values="-$rock_amplitude 0; $rock_amplitude 0; -$rock_amplitude 0" keyTimes="0; 0.5; 1" calcMode="spline" keySplines="0.42 0 0.58 1; 0.42 0 0.58 1" dur="${rock_dur}s" repeatCount="indefinite"/>
      <g>
        <animateTransform attributeName="transform" type="translate" values="$bounce_values" dur="${bounce_dur}s" repeatCount="indefinite" additive="sum"/>
        <image href="$image_uri" x="$img_x" y="$img_y" width="$img_width" height="$img_height" preserveAspectRatio="xMidYMid meet"/>
      </g>
    </g>
  </g>
