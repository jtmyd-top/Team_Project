<template>
  <div class="group-management-panel">
    <!-- Header -->
    <div class="panel-header">
      <h2>群组管理</h2>
      <el-button @click="$emit('close')" type="text" class="close-btn">
        <el-icon><Close /></el-icon>
      </el-button>
    </div>

    <!-- Tabs -->
    <el-tabs v-model="activeTab" class="management-tabs">
      <!-- Basic Info Tab -->
      <el-tab-pane label="基本信息" name="info">
        <div class="tab-content">
          <el-form :model="groupForm" label-width="80px" label-position="top">
            <el-form-item label="群组名称">
              <el-input
                v-model="groupForm.name"
                maxlength="80"
                show-word-limit
                :disabled="!canEdit"
              />
            </el-form-item>

            <el-form-item label="群组头像">
              <el-upload
                class="avatar-uploader"
                :action="uploadUrl"
                :headers="uploadHeaders"
                :show-file-list="false"
                :on-success="handleAvatarSuccess"
                :before-upload="beforeAvatarUpload"
                :disabled="!canEdit"
              >
                <img v-if="groupForm.avatar" :src="groupForm.avatar" class="avatar">
                <el-icon v-else class="avatar-uploader-icon"><Plus /></el-icon>
              </el-upload>
            </el-form-item>

            <el-form-item label="群简介">
              <el-input
                v-model="groupForm.description"
                type="textarea"
                :rows="3"
                maxlength="200"
                show-word-limit
                :disabled="!canEdit"
              />
            </el-form-item>

            <el-form-item label="群公告">
              <el-input
                v-model="groupForm.announcement"
                type="textarea"
                :rows="4"
                maxlength="500"
                show-word-limit
                :disabled="!canEdit"
              />
            </el-form-item>

            <el-form-item v-if="canEdit">
              <el-button type="primary" @click="saveGroupInfo" :loading="saving">
                保存修改
              </el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>

      <!-- Members Tab -->
      <el-tab-pane label="成员管理" name="members">
        <div class="tab-content">
          <div class="members-header">
            <el-input
              v-model="memberSearch"
              placeholder="搜索成员"
              clearable
              class="search-input"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-button
              v-if="canInvite"
              type="primary"
              @click="showInviteDialog = true"
            >
              <el-icon><Plus /></el-icon>
              邀请成员
            </el-button>
          </div>

          <div class="members-list">
            <div
              v-for="member in filteredMembers"
              :key="member.user_id"
              class="member-item"
            >
              <div class="member-info">
                <el-avatar :src="member.avatar" :size="40">
                  {{ member.username[0] }}
                </el-avatar>
                <div class="member-details">
                  <div class="member-name">
                    {{ member.username }}
                    <el-tag v-if="member.role === 'owner'" type="danger" size="small">群主</el-tag>
                    <el-tag v-else-if="member.role === 'admin'" type="warning" size="small">管理员</el-tag>
                  </div>
                  <div class="member-meta">
                    加入时间: {{ formatDate(member.joined_at) }}
                  </div>
                </div>
              </div>

              <div class="member-actions" v-if="canManageMember(member)">
                <el-dropdown @command="handleMemberAction($event, member)">
                  <el-button type="text">
                    <el-icon><More /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item
                        v-if="isOwner && member.role === 'member'"
                        command="promote"
                      >
                        设为管理员
                      </el-dropdown-item>
                      <el-dropdown-item
                        v-if="isOwner && member.role === 'admin'"
                        command="demote"
                      >
                        取消管理员
                      </el-dropdown-item>
                      <el-dropdown-item
                        v-if="canMuteMember(member) && member.is_group_muted"
                        command="unmute"
                      >
                        解除禁言
                      </el-dropdown-item>
                      <el-dropdown-item
                        v-if="canMuteMember(member)"
                        disabled
                      >
                        {{ member.is_group_muted ? '延长禁言' : '禁言时长' }}
                      </el-dropdown-item>
                      <el-dropdown-item
                        v-for="option in muteDurationOptions"
                        v-if="canMuteMember(member)"
                        :key="option.value"
                        :command="`mute:${option.value}`"
                      >
                        {{ option.label }}
                      </el-dropdown-item>
                      <el-dropdown-item
                        v-if="canBanMember(member)"
                        command="ban"
                      >
                        封禁
                      </el-dropdown-item>
                      <el-dropdown-item
                        v-if="canRemoveMember(member)"
                        command="remove"
                        divided
                      >
                        移除成员
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- Permissions Tab -->
      <el-tab-pane label="权限设置" name="permissions" v-if="canEdit">
        <div class="tab-content">
          <el-form label-width="120px">
            <el-form-item label="发言模式">
              <el-radio-group v-model="groupForm.mute_mode" :disabled="!isOwner">
                <el-radio label="none">所有人可发言</el-radio>
                <el-radio label="admins_only">仅管理员可发言</el-radio>
              </el-radio-group>
              <div class="form-tip">全体禁言时，只有群主和管理员可以发送消息</div>
            </el-form-item>

            <el-form-item v-if="isOwner">
              <el-button type="primary" @click="savePermissions" :loading="saving">
                保存权限设置
              </el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>

      <!-- Invites Tab -->
      <el-tab-pane label="邀请链接" name="invites" v-if="canInvite">
        <div class="tab-content">
          <div class="invites-header">
            <el-button type="primary" @click="createInviteLink">
              <el-icon><Link /></el-icon>
              创建邀请链接
            </el-button>
          </div>

          <div class="invites-list">
            <div
              v-for="invite in inviteLinks"
              :key="invite.token"
              class="invite-item"
            >
              <div class="invite-info">
                <div class="invite-link">
                  {{ getInviteUrl(invite.token) }}
                </div>
                <div class="invite-meta">
                  <span>创建者: {{ invite.created_by_username }}</span>
                  <span v-if="invite.expires_at">
                    过期时间: {{ formatDate(invite.expires_at) }}
                  </span>
                  <span v-else>永不过期</span>
                  <span v-if="invite.max_uses">
                    使用次数: {{ invite.uses_count }}/{{ invite.max_uses }}
                  </span>
                  <span v-else>
                    使用次数: {{ invite.uses_count }}
                  </span>
                </div>
              </div>
              <div class="invite-actions">
                <el-button
                  type="text"
                  @click="copyInviteLink(invite.token)"
                >
                  复制
                </el-button>
                <el-button
                  type="text"
                  @click="revokeInvite(invite.token)"
                  :disabled="!!invite.revoked_at"
                >
                  {{ invite.revoked_at ? '已撤销' : '撤销' }}
                </el-button>
              </div>
            </div>
          </div>
        </div>
      </el-tab-pane>

      <!-- Danger Zone Tab -->
      <el-tab-pane label="危险操作" name="danger" v-if="isOwner">
        <div class="tab-content danger-zone">
          <el-alert
            title="危险操作区域"
            type="warning"
            description="以下操作不可恢复，请谨慎操作"
            :closable="false"
            show-icon
          />

          <div class="danger-actions">
            <div class="danger-action-item">
              <div>
                <h4>转让群主</h4>
                <p>将群主权限转让给其他成员，您将成为普通管理员</p>
              </div>
              <el-button type="warning" @click="showTransferDialog = true">
                转让群主
              </el-button>
            </div>

            <div class="danger-action-item">
              <div>
                <h4>解散群组</h4>
                <p>永久删除此群组，所有成员将被移除，所有消息将被清空</p>
              </div>
              <el-button type="danger" @click="confirmDissolve">
                解散群组
              </el-button>
            </div>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- Transfer Ownership Dialog -->
    <TransferOwnershipDialog
      v-model="showTransferDialog"
      :group-id="groupId"
      :members="members"
      @success="handleTransferSuccess"
    />

    <!-- Ban Member Dialog -->
    <BanMemberDialog
      v-model="showBanDialog"
      :group-id="groupId"
      :member="selectedMember"
      @success="handleBanSuccess"
    />

    <!-- Invite Preview Dialog -->
    <InvitePreviewDialog
      v-model="showInviteDialog"
      :group-id="groupId"
      @success="handleInviteCreated"
    />
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Close, Plus, Search, More, Link } from '@element-plus/icons-vue';
import TransferOwnershipDialog from './TransferOwnershipDialog.vue';
import BanMemberDialog from './BanMemberDialog.vue';
import InvitePreviewDialog from './InvitePreviewDialog.vue';
import { getCsrfToken } from '../../../utils/csrf';

export default {
  name: 'GroupManagementPanel',
  components: {
    Close,
    Plus,
    Search,
    More,
    Link,
    TransferOwnershipDialog,
    BanMemberDialog,
    InvitePreviewDialog,
  },
  props: {
    groupId: {
      type: Number,
      required: true,
    },
    currentUserId: {
      type: Number,
      required: true,
    },
  },
  emits: ['close', 'update'],
  setup(props, { emit }) {
    const activeTab = ref('info');
    const saving = ref(false);
    const memberSearch = ref('');

    const groupForm = ref({
      name: '',
      avatar: '',
      description: '',
      announcement: '',
      mute_mode: 'none',
    });

    const members = ref([]);
    const inviteLinks = ref([]);
    const currentUserRole = ref('member');
    const muteDurationOptions = [
      { label: '10 分钟', value: 10 },
      { label: '30 分钟', value: 30 },
      { label: '1 小时', value: 60 },
      { label: '3 小时', value: 180 },
      { label: '6 小时', value: 360 },
      { label: '24 小时', value: 1440 },
      { label: '永久禁言', value: 'permanent' },
    ];

    const showTransferDialog = ref(false);
    const showBanDialog = ref(false);
    const showInviteDialog = ref(false);
    const selectedMember = ref(null);

    // Computed
    const isOwner = computed(() => currentUserRole.value === 'owner');
    const isAdmin = computed(() => ['owner', 'admin'].includes(currentUserRole.value));
    const canEdit = computed(() => isAdmin.value);
    const canInvite = computed(() => isAdmin.value);

    const filteredMembers = computed(() => {
      if (!memberSearch.value) return members.value;
      const search = memberSearch.value.toLowerCase();
      return members.value.filter(m =>
        m.username.toLowerCase().includes(search)
      );
    });

    const uploadUrl = computed(() => '/api/messages/groups/upload-avatar/');
    const uploadHeaders = computed(() => ({
      'X-CSRFToken': getCsrfToken(),
    }));

    // Methods
    const loadGroupInfo = async () => {
      try {
        const resp = await fetch(`/api/messages/groups/${props.groupId}/`);
        const data = await resp.json();
        if (data.status === 'success') {
          groupForm.value = {
            name: data.group.name,
            avatar: data.group.avatar,
            description: data.group.description || '',
            announcement: data.group.announcement || '',
            mute_mode: data.group.mute_mode || 'none',
          };
          currentUserRole.value = data.membership.role;
        }
      } catch (error) {
        console.error('加载群组信息失败:', error);
        ElMessage.error('加载群组信息失败');
      }
    };

    const loadMembers = async () => {
      try {
        const resp = await fetch(`/api/messages/groups/${props.groupId}/members/`);
        const data = await resp.json();
        if (data.status === 'success') {
          members.value = data.members;
        }
      } catch (error) {
        console.error('加载成员列表失败:', error);
      }
    };

    const loadInviteLinks = async () => {
      try {
        const resp = await fetch(`/api/messages/groups/${props.groupId}/invites/`);
        const data = await resp.json();
        if (data.status === 'success') {
          inviteLinks.value = data.invites;
        }
      } catch (error) {
        console.error('加载邀请链接失败:', error);
      }
    };

    const saveGroupInfo = async () => {
      saving.value = true;
      try {
        const resp = await fetch(`/api/messages/groups/${props.groupId}/update/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify({
            name: groupForm.value.name,
            description: groupForm.value.description,
            announcement: groupForm.value.announcement,
          }),
        });
        const data = await resp.json();
        if (data.status === 'success') {
          ElMessage.success('保存成功');
          emit('update');
        } else {
          ElMessage.error(data.error || '保存失败');
        }
      } catch (error) {
        console.error('保存失败:', error);
        ElMessage.error('保存失败');
      } finally {
        saving.value = false;
      }
    };

    const savePermissions = async () => {
      saving.value = true;
      try {
        const resp = await fetch(`/api/messages/groups/${props.groupId}/update/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify({
            mute_mode: groupForm.value.mute_mode,
          }),
        });
        const data = await resp.json();
        if (data.status === 'success') {
          ElMessage.success('权限设置已保存');
        } else {
          ElMessage.error(data.error || '保存失败');
        }
      } catch (error) {
        console.error('保存权限设置失败:', error);
        ElMessage.error('保存失败');
      } finally {
        saving.value = false;
      }
    };

    const handleAvatarSuccess = (response) => {
      if (response.status === 'success') {
        groupForm.value.avatar = response.url;
        ElMessage.success('头像上传成功');
      }
    };

    const beforeAvatarUpload = (file) => {
      const isImage = file.type.startsWith('image/');
      const isLt2M = file.size / 1024 / 1024 < 2;

      if (!isImage) {
        ElMessage.error('只能上传图片文件!');
        return false;
      }
      if (!isLt2M) {
        ElMessage.error('图片大小不能超过 2MB!');
        return false;
      }
      return true;
    };

    const canManageMember = (member) => {
      if (member.user_id === props.currentUserId) return false;
      if (member.role === 'owner') return false;
      if (isOwner.value) return true;
      if (isAdmin.value && member.role === 'member') return true;
      return false;
    };

    const canMuteMember = (member) => {
      return canManageMember(member) && member.role !== 'admin';
    };

    const canBanMember = (member) => {
      return canManageMember(member);
    };

    const canRemoveMember = (member) => {
      return canManageMember(member);
    };

    const handleMemberAction = async (command, member) => {
      selectedMember.value = member;

      switch (command) {
        case 'promote':
          await updateMemberRole(member.user_id, 'admin');
          break;
        case 'demote':
          await updateMemberRole(member.user_id, 'member');
          break;
        case 'unmute':
          await updateMemberMute(member.user_id, null);
          break;
        case 'ban':
          showBanDialog.value = true;
          break;
        case 'remove':
          await removeMember(member.user_id);
          break;
        default:
          if (typeof command === 'string' && command.startsWith('mute:')) {
            await updateMemberMute(member.user_id, command.slice(5));
          }
      }
    };

    const updateMemberMute = async (userId, duration) => {
      try {
        const payload = duration === null
          ? { action: 'unmute' }
          : duration === 'permanent'
            ? { duration: 'permanent' }
            : { duration_minutes: Number(duration) };
        const resp = await fetch(`/api/messages/groups/${props.groupId}/members/${userId}/mute/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify(payload),
        });
        const data = await resp.json();
        if (data.status === 'success') {
          ElMessage.success(duration === null ? '已解除禁言' : '已禁言');
          await loadMembers();
          emit('update');
        } else {
          ElMessage.error(data.error || '操作失败');
        }
      } catch (error) {
        console.error('更新禁言状态失败:', error);
        ElMessage.error('操作失败');
      }
    };

    const updateMemberRole = async (userId, newRole) => {
      try {
        const resp = await fetch(`/api/messages/groups/${props.groupId}/members/${userId}/role/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify({ role: newRole }),
        });
        const data = await resp.json();
        if (data.status === 'success') {
          ElMessage.success('角色更新成功');
          await loadMembers();
        } else {
          ElMessage.error(data.error || '更新失败');
        }
      } catch (error) {
        console.error('更新角色失败:', error);
        ElMessage.error('操作失败');
      }
    };

    const removeMember = async (userId) => {
      try {
        await ElMessageBox.confirm('确定要移除此成员吗？', '确认移除', {
          type: 'warning',
        });

        const resp = await fetch(`/api/messages/groups/${props.groupId}/members/${userId}/remove/`, {
          method: 'POST',
          headers: {
            'X-CSRFToken': getCsrfToken(),
          },
        });
        const data = await resp.json();
        if (data.status === 'success') {
          ElMessage.success('成员已移除');
          await loadMembers();
        } else {
          ElMessage.error(data.error || '移除失败');
        }
      } catch (error) {
        if (error !== 'cancel') {
          console.error('移除成员失败:', error);
          ElMessage.error('操作失败');
        }
      }
    };

    const createInviteLink = async () => {
      showInviteDialog.value = true;
    };

    const getInviteUrl = (token) => {
      return `${window.location.origin}/messages/groups/join/${token}`;
    };

    const copyInviteLink = async (token) => {
      const url = getInviteUrl(token);
      try {
        await navigator.clipboard.writeText(url);
        ElMessage.success('邀请链接已复制');
      } catch (error) {
        console.error('复制失败:', error);
        ElMessage.error('复制失败');
      }
    };

    const revokeInvite = async (token) => {
      try {
        await ElMessageBox.confirm('确定要撤销此邀请链接吗？', '确认撤销', {
          type: 'warning',
        });

        const resp = await fetch(`/api/messages/groups/${props.groupId}/invites/${token}/revoke/`, {
          method: 'POST',
          headers: {
            'X-CSRFToken': getCsrfToken(),
          },
        });
        const data = await resp.json();
        if (data.status === 'success') {
          ElMessage.success('邀请链接已撤销');
          await loadInviteLinks();
        } else {
          ElMessage.error(data.error || '撤销失败');
        }
      } catch (error) {
        if (error !== 'cancel') {
          console.error('撤销邀请失败:', error);
          ElMessage.error('操作失败');
        }
      }
    };

    const confirmDissolve = async () => {
      try {
        await ElMessageBox.confirm(
          '解散群组后，所有数据将被永久删除且无法恢复。请输入群组名称确认解散。',
          '确认解散群组',
          {
            confirmButtonText: '确定解散',
            cancelButtonText: '取消',
            type: 'error',
            inputPattern: new RegExp(`^${groupForm.value.name}$`),
            inputPlaceholder: '请输入群组名称',
            inputErrorMessage: '群组名称不匹配',
          }
        );

        await dissolveGroup();
      } catch (error) {
        // User cancelled
      }
    };

    const dissolveGroup = async () => {
      try {
        const resp = await fetch(`/api/messages/groups/${props.groupId}/dissolve/`, {
          method: 'POST',
          headers: {
            'X-CSRFToken': getCsrfToken(),
          },
        });
        const data = await resp.json();
        if (data.status === 'success') {
          ElMessage.success('群组已解散');
          emit('close');
          emit('update');
        } else {
          ElMessage.error(data.error || '解散失败');
        }
      } catch (error) {
        console.error('解散群组失败:', error);
        ElMessage.error('操作失败');
      }
    };

    const handleTransferSuccess = () => {
      ElMessage.success('群主转让成功');
      loadGroupInfo();
      loadMembers();
    };

    const handleBanSuccess = () => {
      ElMessage.success('成员已封禁');
      loadMembers();
    };

    const handleInviteCreated = () => {
      loadInviteLinks();
    };

    const formatDate = (dateStr) => {
      if (!dateStr) return '';
      const date = new Date(dateStr);
      return date.toLocaleString('zh-CN');
    };

    onMounted(() => {
      loadGroupInfo();
      loadMembers();
      if (canInvite.value) {
        loadInviteLinks();
      }
    });

    return {
      activeTab,
      saving,
      memberSearch,
      groupForm,
      members,
      inviteLinks,
      currentUserRole,
      muteDurationOptions,
      showTransferDialog,
      showBanDialog,
      showInviteDialog,
      selectedMember,
      isOwner,
      isAdmin,
      canEdit,
      canInvite,
      filteredMembers,
      uploadUrl,
      uploadHeaders,
      saveGroupInfo,
      savePermissions,
      handleAvatarSuccess,
      beforeAvatarUpload,
      canManageMember,
      canMuteMember,
      canBanMember,
      canRemoveMember,
      handleMemberAction,
      createInviteLink,
      getInviteUrl,
      copyInviteLink,
      revokeInvite,
      confirmDissolve,
      handleTransferSuccess,
      handleBanSuccess,
      handleInviteCreated,
      formatDate,
    };
  },
};
</script>

<style scoped>
.group-management-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #fff;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #e8e8e8;
}

.panel-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.close-btn {
  font-size: 20px;
}

.management-tabs {
  flex: 1;
  overflow: hidden;
}

.management-tabs :deep(.el-tabs__content) {
  height: calc(100% - 55px);
  overflow-y: auto;
}

.tab-content {
  padding: 20px;
}

/* Avatar Uploader */
.avatar-uploader :deep(.el-upload) {
  border: 1px dashed #d9d9d9;
  border-radius: 6px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition: border-color 0.3s;
}

.avatar-uploader :deep(.el-upload:hover) {
  border-color: #409eff;
}

.avatar-uploader-icon {
  font-size: 28px;
  color: #8c939d;
  width: 120px;
  height: 120px;
  display: flex;
  justify-content: center;
  align-items: center;
}

.avatar {
  width: 120px;
  height: 120px;
  display: block;
  object-fit: cover;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
}

/* Members */
.members-header {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.search-input {
  flex: 1;
}

.members-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.member-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  transition: background-color 0.2s;
}

.member-item:hover {
  background-color: #f5f7fa;
}

.member-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.member-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.member-name {
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
}

.member-meta {
  font-size: 12px;
  color: #909399;
}

/* Invites */
.invites-header {
  margin-bottom: 16px;
}

.invites-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.invite-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  border: 1px solid #e8e8e8;
  border-radius: 8px;
}

.invite-info {
  flex: 1;
}

.invite-link {
  font-family: monospace;
  font-size: 12px;
  color: #409eff;
  margin-bottom: 8px;
  word-break: break-all;
}

.invite-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: #909399;
}

.invite-actions {
  display: flex;
  gap: 8px;
}

/* Danger Zone */
.danger-zone {
  max-width: 600px;
}

.danger-actions {
  margin-top: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.danger-action-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border: 1px solid #f5c6cb;
  border-radius: 8px;
  background-color: #fff5f5;
}

.danger-action-item h4 {
  margin: 0 0 8px 0;
  font-size: 16px;
  color: #f56c6c;
}

.danger-action-item p {
  margin: 0;
  font-size: 14px;
  color: #909399;
}
</style>
