引入 textual 之后带来的问题

P1 level
- [x] 无法高亮当前句子，TTS也无法播放
- [ ] TOC 界面无法上下移动










还存在的几个其他问题

P1 level

- [ ] 在 table of contents UI 中，第一次点击上下按钮没有效果，而且最后选中的章节不是当前选中的章节，而是他下面的一个章节。

- [ ] 在 AI Assistant 的界面，当我退出这个界面，然后移动到下一句的时候，然后重新打开 AI Assistant 的界面，这时候显示的 Current Sentence 还是是现在的这个 sentence，但是和 AI 的交互的内容还是跟之前的那句话相关的。 


P2 level
- [*] 在 Table of contents 页面里面，点击ESC按键不会关闭TOC界面，但是点击C按键会。
- [ ] 在reader界面中，TTS每读完一个句子，屏幕都会闪烁一次。
- [*] AI assitant UI中每输入一个文字，界面就会闪烁一次



DONE:

- [*] table of contents UI中的内容超出了边界线，而且按下enter键无法跳转到相应的章节。

- [x] AI assitant UI界面外边界线的颜色和reader、table of contents UI界面外边界线的颜色不一致。

- [x] 在 AI assitant UI界面中，每次输入任何文字，屏幕都会闪烁一次。

- [*] AI assitant UI和table of contents UI界面中的title没有正确显示，我猜测可能是因为这个界面的高度超过了命令行console的高度，导致顶部的内容被隐藏了，但是底部边界线之外却有空白。而且在拉长命令行界面高度的时候，title会闪现一下。

- [*] AI assitant UI和table of contents UI界面中esc键没有效果

- [*] 在 Table of contents 页面里面，我输入上下按键也会把这个界面给关掉。 

- [x] AI assitant UI中，每次点击屏幕，都会关闭AI assitant UI界面。