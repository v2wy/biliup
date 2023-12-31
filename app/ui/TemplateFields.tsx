import React, {useState} from "react";
import {FormFCChild} from "@douyinfe/semi-ui/lib/es/form";
import {IconChevronDown, IconChevronUp} from "@douyinfe/semi-icons";
import {Avatar, Button, Collapsible, Form, Space, Typography} from "@douyinfe/semi-ui";
import useSWR from "swr";
import {BiliType, fetcher, StudioEntity} from "../lib/api-streamer";
import {useBiliUsers, useTypeTree} from "../lib/use-streamers";

const TemplateFields: React.FC<FormFCChild> = ({ formState, formApi, values }) => {
    const { Section, Input, DatePicker, TimePicker, Select, Switch, InputNumber, Checkbox, CheckboxGroup, RadioGroup, Radio, Cascader, TagInput, TextArea } = Form;
    const { Text } = Typography;
    const { typeTree, isError, isLoading } = useTypeTree();
    const treeData = typeTree?.map((type: BiliType) => {
        return {
            ...type,
            children: type.children.map(cType => {
                return {
                    label: <>{cType.name} <Text type="quaternary" size='small'>{cType.desc}</Text></>,
                    value: cType.id,
                };
            })
        }
    })
    const collapsed = (<>
        <CheckboxGroup field='sound' options={[
            { label: '杜比音效', value: 'dolby' },
            { label: 'Hi-Res无损音质', value: 'lossless_music' },
        ]} direction='horizontal' label='音效设置' />
        <CheckboxGroup field='interaction' options={[
            { label: '关闭弹幕', value: 'up_close_danmu' },
            { label: '关闭评论', value: 'up_close_reply' },
            { label: '开启精选评论', value: 'up_selection_reply' },
        ]} direction='horizontal' label='互动设置' />
        <Input field='dynamic' label='粉丝动态' style={{width: 464}}/>
    </>);
    const [isOpen, setOpen] = useState(false);
    const {biliUsers} = useBiliUsers();
    const list = biliUsers?.map((item) => {
        return {
            value: item.value, label: <>
                <Avatar size="extra-small" src={item.face} />
                <span style={{ marginLeft: 8 }}>
                    {item.name}
                </span></>
        }
    })
    const toggle = () => {
        setOpen(!isOpen);
        formApi.scrollToField('isDtime');
    };
    return(
        <>
            <Section text={'基本信息'}>
                <Input rules={[
                    { required: true }
                ]} field='template_name' label='模板名称' style={{width: 464}}/>
                <Form.Select rules={[
                    { required: true }
                ]} field="user" label={{ text: '投稿账号' }} style={{ width: 176 }} optionList={list} />
            </Section>
            <Section text={'基本设置'} >
                <Input field='title' label='视频标题' style={{width: 464}} placeholder='稿件标题'/>
                <RadioGroup
                    field="copyright"
                    label='类型'
                    direction='vertical'
                    // initValue={1}
                >
                    <div onClick={()=>formApi.setValue('source', '')}>
                        <Radio value={1}>自制</Radio>
                    </div>
                    <Radio value={2} style={{alignItems: 'center', flexShrink: 0}}>
                        <span style={{flexShrink: 0}}>转载</span>
                        {/* <div > */}
                        <Input field='source' onClick={()=>formApi.setValue('copyright', 2)} placeholder="转载视频请注明来源（例：转自http://www.xx.com/yy）注明来源会更快地通过审核哦" noLabel fieldStyle={{padding: 0, marginLeft: 24, width: 560}}/>
                        {/* </div> */}

                        {/* <Form.DatePicker type='dateTimeRange' noLabel field='customTime'/> */}
                    </Radio>
                </RadioGroup>
                <Cascader
                    field="tid"
                    label='分区'
                    style={{ width: 272 }}
                    treeData={treeData}
                    placeholder="投稿分区"
                    dropdownStyle={{ maxWidth:670 }}
                    rules={[
                        { required: true }
                    ]}
                />
                <TagInput
                    field="tag"
                    label='标签'
                    placeholder='输入标签，Enter 确定'
                    onChange={v => console.log(v)}
                    style={{width: 560}}
                />
                <TextArea style={{maxWidth: 560}}
                    field="description" label='简介' placeholder="填写更全面的相关信息，让更多的人能找到你的视频吧"
                    autosize maxCount={2000} showClear/>

                <div style={{display: 'flex', alignItems: 'center', color: 'var(--semi-color-tertiary)'}}>
                    <Switch field='isDtime' label={{ text: '定时发布' }} checkedText="｜" uncheckedText="〇"/>
                    <span style={{paddingLeft: 12, fontSize: 12}}>(当前+2小时 ≤ 可选时间 ≤ 当前+15天，转载稿件撞车判定以过审发布时间为准)</span>
                </div>
                {values.isDtime === true ? (
                    <DatePicker field="dtime" label=' ' type='dateTime' fieldStyle={{ paddingTop: 0 }} />
                ) : null}
            </Section>

            <Section style={{paddingBottom: 40}} text={<div style={{cursor: 'pointer'}} onClick={toggle}>更多设置 {isOpen? <IconChevronUp style={{marginLeft: 12}} />:<IconChevronDown style={{marginLeft: 12}} />}</div>}>
                <Collapsible isOpen={isOpen} >
                    {collapsed}
                </Collapsible>
            </Section>
        </>
    );};

export default TemplateFields;